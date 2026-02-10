"""Full TTS text preprocessing pipeline.

Order:
1. Normalize (numbers, abbreviations, cleanup)
2. Yofikate (restore ё)
3. Apply russtress (accent marks U+0301, skip monosyllabic & already-processed)
4. Apply post_overrides (stress corrections from /fix command)
"""

import codecs
import logging
import os
import re

from num2words import num2words
from sqlalchemy import select

from bot.database import async_session
from bot.models.stress_override import StressOverride, StressUnknown

logger = logging.getLogger(__name__)

# ── Vowels for stress logic ──
RUSSIAN_VOWELS = set("аеёиоуыэюяАЕЁИОУЫЭЮЯ")
COMBINING_ACCENT = "\u0301"  # ◌́

# ── Monosyllabic / function words — do NOT stress ──
SKIP_STRESS = {
    "а", "б", "в", "г", "д", "е", "ж", "з", "и", "й", "к", "л", "м",
    "н", "о", "п", "р", "с", "т", "у", "ф", "х", "ц", "ч", "ш", "щ",
    "да", "но", "ты", "мы", "вы", "он", "их", "им", "на", "не", "ни",
    "же", "ли", "бы", "уж", "аж", "ну", "ой", "эй", "по", "до", "от",
    "за", "из", "ко", "со", "об", "то", "те", "та", "ту", "тот",
    "что", "кто", "как", "где", "вот", "вон", "раз", "при", "без",
    "для", "под", "над", "про", "или", "ещё", "еще", "уже",
    "это", "она", "они", "его", "ему", "ей", "её", "ее",
    "нас", "вас", "нам", "вам", "мне", "тут", "там",
    "сей", "чей", "мой", "наш", "ваш", "мою", "нём",
    "так", "тем", "чем", "ведь", "лишь", "пусть", "даже",
    "был", "быт", "быть",
}

# ── Abbreviation expansion ──
ABBREVIATIONS = {
    "ООО": "общество с ограниченной ответственностью",
    "ИП": "индивидуальный предприниматель",
    "РФ": "Российская Федерация",
    "МВД": "эм вэ дэ",
    "ФСБ": "эф эс бэ",
    "ЦБ": "центральный банк",
    "ВВП": "вэ вэ пэ",
    "США": "сэ шэ а",
    "ЕС": "е эс",
    "ООН": "о о эн",
    "ВОЗ": "вэ о зэ",
    "ИИ": "искусственный интеллект",
    "AI": "эй ай",
    "API": "эй пи ай",
    "URL": "ю эр эл",
    "PDF": "пи ди эф",
    "USB": "ю эс би",
    "SMS": "эс эм эс",
    "ул.": "улица",
    "д.": "дом",
    "г.": "город",
    "пр.": "проспект",
    "т.д.": "так далее",
    "т.п.": "тому подобное",
    "т.е.": "то есть",
    "т.к.": "так как",
    "т.н.": "так называемый",
    "и т.д.": "и так далее",
    "и т.п.": "и тому подобное",
    "с.": "страница",
    "руб.": "рублей",
    "коп.": "копеек",
    "тыс.": "тысяч",
    "млн.": "миллионов",
    "млн": "миллионов",
    "млрд.": "миллиардов",
    "млрд": "миллиардов",
    "трлн": "триллионов",
    "км": "километров",
    "кг": "килограмм",
    "г": "грамм",
    "м": "метров",
    "см": "сантиметров",
    "мм": "миллиметров",
}


class TTSPipeline:
    """Stateful TTS text preprocessor with caching."""

    def __init__(self):
        self._yo_dict: dict[str, str] | None = None
        self._overrides_cache: dict[str, str] | None = None
        self._accent_model = None
        self._accent_loaded = False

    # ═══════════════════════════════════════════════════════
    #  1. NORMALIZATION
    # ═══════════════════════════════════════════════════════

    def normalize(self, text: str) -> str:
        """Normalize numbers, abbreviations, symbols."""
        # Protect URLs, emails, code blocks
        protected: list[tuple[str, str]] = []
        url_re = re.compile(r'https?://\S+|www\.\S+|\S+@\S+\.\S+')
        for i, m in enumerate(url_re.finditer(text)):
            placeholder = f"__URL{i}__"
            protected.append((placeholder, m.group()))
        for ph, orig in protected:
            text = text.replace(orig, ph)

        # №
        text = re.sub(r'№\s*', 'номер ', text)

        # Currency: 77 рублей, $100
        text = re.sub(
            r'\$\s*(\d[\d\s,.]*)',
            lambda m: num2words(self._parse_num(m.group(1)), lang='ru') + ' долларов',
            text,
        )
        text = re.sub(
            r'€\s*(\d[\d\s,.]*)',
            lambda m: num2words(self._parse_num(m.group(1)), lang='ru') + ' евро',
            text,
        )

        # Numbers: "77" → "семьдесят семь" (don't consume trailing spaces)
        text = re.sub(
            r'\d[\d,.]*',
            lambda m: self._num_to_words(m.group()),
            text,
        )

        # Abbreviations (longer first, all with word-boundary matching)
        for abbr in sorted(ABBREVIATIONS.keys(), key=len, reverse=True):
            if abbr in text:
                text = re.sub(
                    r'(?<![а-яёА-ЯЁa-zA-Z])' + re.escape(abbr) + r'(?![а-яёА-ЯЁa-zA-Z])',
                    ABBREVIATIONS[abbr], text
                )

        # Cleanup: markdown artifacts, excessive whitespace
        text = re.sub(r'[*_~`#>]', '', text)
        text = re.sub(r'\s{2,}', ' ', text)
        text = text.strip()

        # Restore protected tokens
        for ph, orig in protected:
            text = text.replace(ph, orig)

        return text

    @staticmethod
    def _parse_num(s: str) -> float:
        s = s.replace(' ', '').replace(',', '.')
        try:
            return float(s)
        except ValueError:
            return 0

    @staticmethod
    def _num_to_words(s: str) -> str:
        s_clean = s.strip().replace(' ', '')
        if not s_clean:
            return s
        try:
            if '.' in s_clean or ',' in s_clean:
                val = float(s_clean.replace(',', '.'))
                if val == int(val):
                    return num2words(int(val), lang='ru')
                return num2words(val, lang='ru')
            return num2words(int(s_clean), lang='ru')
        except (ValueError, OverflowError):
            return s

    # ═══════════════════════════════════════════════════════
    #  2. YOFIKATION (restore ё)
    # ═══════════════════════════════════════════════════════

    def _load_yo_dict(self):
        """Load yo.dat dictionary."""
        if self._yo_dict is not None:
            return
        self._yo_dict = {}
        dat_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'yo.dat')
        if not os.path.exists(dat_path):
            logger.warning("yo.dat not found at %s", dat_path)
            return
        with codecs.open(dat_path, "r", "utf-8") as f:
            for line in f:
                if "*" in line:
                    continue
                cline = line.rstrip('\n')
                if "(" in cline:
                    bline, sline = cline.split("(", 1)
                    sline = sline.rstrip(')')
                else:
                    bline = cline
                    sline = ""
                if "|" in sline:
                    for suffix in sline.split("|"):
                        value = bline + suffix
                        key = value.replace('ё', 'е').replace('Ё', 'Е')
                        self._yo_dict[key] = value
                else:
                    value = bline + sline
                    key = value.replace('ё', 'е').replace('Ё', 'Е')
                    self._yo_dict[key] = value
        logger.info("Yofikator: loaded %d entries", len(self._yo_dict))

    def yofikate(self, text: str) -> str:
        """Restore ё where unambiguous."""
        self._load_yo_dict()
        if not self._yo_dict:
            return text
        tokens = re.findall(r'\w+|\W+', text, re.UNICODE)
        result = []
        for token in tokens:
            replacement = self._yo_dict.get(token)
            if replacement is None:
                replacement = self._yo_dict.get(token.lower())
                if replacement and token[0].isupper():
                    replacement = replacement[0].upper() + replacement[1:]
            result.append(replacement if replacement else token)
        return ''.join(result)

    # ═══════════════════════════════════════════════════════
    #  3. RUSSTRESS (accent marks)
    # ═══════════════════════════════════════════════════════

    def _load_accent_model(self):
        """Lazy-load russtress model."""
        if self._accent_loaded:
            return
        self._accent_loaded = True
        try:
            os.environ['TF_USE_LEGACY_KERAS'] = '1'
            # Suppress TF warnings
            os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
            from russtress import Accent
            self._accent_model = Accent()
            logger.info("russtress model loaded")
        except Exception:
            logger.exception("Failed to load russtress")
            self._accent_model = None

    def _count_vowels(self, word: str) -> int:
        return sum(1 for c in word if c in RUSSIAN_VOWELS)

    def _has_accent(self, word: str) -> bool:
        """Check if word already has combining accent mark."""
        return COMBINING_ACCENT in word

    def _is_russian(self, word: str) -> bool:
        return any('\u0400' <= c <= '\u04ff' for c in word)

    async def apply_stress(self, text: str) -> tuple[str, list[str]]:
        """Apply russtress. Returns (stressed_text, unknown_words)."""
        self._load_accent_model()
        if not self._accent_model:
            return text, []

        unknown_words: list[str] = []

        def stress_word(match: re.Match) -> str:
            word = match.group()
            lower = word.lower().replace(COMBINING_ACCENT, '')

            # Skip: non-Russian, monosyllabic, function words, already-processed
            if not self._is_russian(word):
                return word
            if self._has_accent(word):
                return word
            if 'ё' in lower or 'Ё' in word:
                return word  # ё is always stressed
            if lower in SKIP_STRESS:
                return word
            if self._count_vowels(word) <= 1:
                return word

            try:
                stressed = self._accent_model.put_stress(word)
                # russtress marks stress with ' after the vowel
                if "'" not in stressed:
                    unknown_words.append(lower)
                    return word

                # Convert ' to combining accent (U+0301)
                result = []
                for ch in stressed:
                    if ch == "'":
                        result.append(COMBINING_ACCENT)
                    else:
                        result.append(ch)
                return ''.join(result)
            except Exception:
                unknown_words.append(lower)
                return word

        result = re.sub(r'[а-яёА-ЯЁ\u0301]+', stress_word, text)
        return result, unknown_words

    # ═══════════════════════════════════════════════════════
    #  4. POST-OVERRIDES (stress corrections from /fix)
    # ═══════════════════════════════════════════════════════

    async def _load_overrides(self):
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(StressOverride).order_by(StressOverride.word)
                )
                self._overrides_cache = {
                    r.word: r.replacement for r in result.scalars().all()
                }
                logger.info("Stress overrides: loaded %d", len(self._overrides_cache))
        except Exception:
            logger.exception("Failed to load stress overrides")
            self._overrides_cache = {}

    def invalidate_overrides_cache(self):
        self._overrides_cache = None

    async def apply_overrides(self, text: str) -> str:
        if self._overrides_cache is None:
            await self._load_overrides()
        for word, replacement in self._overrides_cache.items():
            text = re.sub(
                re.escape(word), replacement, text, flags=re.IGNORECASE
            )
        return text

    # ═══════════════════════════════════════════════════════
    #  LOG UNKNOWN WORDS
    # ═══════════════════════════════════════════════════════

    async def _log_unknown_words(self, words: list[str]):
        if not words:
            return
        try:
            async with async_session() as session:
                for w in set(words):
                    stmt = select(StressUnknown).where(StressUnknown.word == w)
                    result = await session.execute(stmt)
                    existing = result.scalar_one_or_none()
                    if existing:
                        existing.count += 1
                    else:
                        session.add(StressUnknown(word=w, count=1))
                await session.commit()
        except Exception:
            logger.exception("Failed to log unknown stress words")

    # ═══════════════════════════════════════════════════════
    #  FULL PIPELINE
    # ═══════════════════════════════════════════════════════

    async def process(self, text: str) -> str:
        """Full pipeline: normalize → yofikate → stress → overrides."""
        # 1. Normalize
        text = self.normalize(text)

        # 2. Yofikate (restore ё)
        text = self.yofikate(text)

        # 3. Russtress
        text, unknown = await self.apply_stress(text)

        # 4. Post-overrides
        text = await self.apply_overrides(text)

        # Log unknown words
        await self._log_unknown_words(unknown)

        return text
