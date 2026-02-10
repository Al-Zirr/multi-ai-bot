"""Voice service: STT (OpenAI Whisper) + TTS (OpenAI TTS)."""

import logging
import re
from io import BytesIO

from openai import AsyncOpenAI
from sqlalchemy import select, delete

from bot.database import async_session
from bot.models.pronunciation_rule import PronunciationRule
from bot.services.tts_pipeline import TTSPipeline

logger = logging.getLogger(__name__)

OPENAI_TTS_MODEL = "gpt-4o-mini-tts"
TTS_STYLE = "Говори спокойно и уверенно, как мудрый учёный."


class VoiceService:
    def __init__(self, openai_api_key: str, voice_ids: dict[str, str]):
        self.openai_client = AsyncOpenAI(api_key=openai_api_key)
        self.voice_ids = voice_ids
        self.default_voice = next(iter(voice_ids.values())) if voice_ids else "onyx"
        self._pronunciation_cache: list[tuple[re.Pattern, str]] | None = None
        self.pipeline = TTSPipeline()

    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe audio using OpenAI Whisper API."""
        audio_file = BytesIO(audio_bytes)
        audio_file.name = "voice.ogg"

        transcript = await self.openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="ru",
        )
        logger.info("Whisper transcribed %d bytes → %d chars", len(audio_bytes), len(transcript.text))
        return transcript.text

    def get_voice(self, provider: str = "") -> str:
        """Get OpenAI TTS voice name for a given AI provider."""
        return self.voice_ids.get(provider, self.default_voice)

    async def _load_pronunciation_rules(self) -> list[tuple[re.Pattern, str]]:
        """Load pronunciation rules from DB into compiled regex cache."""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(PronunciationRule).order_by(
                        # Longer words first to match "аль-Газали" before "аль"
                        PronunciationRule.word.desc()
                    )
                )
                rows = result.scalars().all()
                rules = []
                for row in sorted(rows, key=lambda r: -len(r.word)):
                    pattern = re.compile(re.escape(row.word), re.IGNORECASE)
                    rules.append((pattern, row.replacement))
                return rules
        except Exception:
            logger.exception("Failed to load pronunciation rules")
            return []

    async def _get_pronunciation_rules(self) -> list[tuple[re.Pattern, str]]:
        """Get cached pronunciation rules, reload if needed."""
        if self._pronunciation_cache is None:
            self._pronunciation_cache = await self._load_pronunciation_rules()
        return self._pronunciation_cache

    def invalidate_pronunciation_cache(self):
        """Force reload of pronunciation rules on next use."""
        self._pronunciation_cache = None

    async def apply_pronunciation(self, text: str) -> str:
        """Apply pronunciation rules to text before TTS."""
        rules = await self._get_pronunciation_rules()
        for pattern, replacement in rules:
            text = pattern.sub(replacement, text)
        return text

    async def add_pronunciation(self, word: str, replacement: str) -> bool:
        """Add or update a pronunciation rule."""
        try:
            async with async_session() as session:
                stmt = select(PronunciationRule).where(
                    PronunciationRule.word == word.lower()
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()
                if existing:
                    existing.replacement = replacement
                else:
                    session.add(PronunciationRule(
                        word=word.lower(), replacement=replacement
                    ))
                await session.commit()
            self.invalidate_pronunciation_cache()
            logger.info("Pronunciation rule: '%s' → '%s'", word, replacement)
            return True
        except Exception:
            logger.exception("Failed to add pronunciation rule")
            return False

    async def remove_pronunciation(self, word: str) -> bool:
        """Remove a pronunciation rule."""
        try:
            async with async_session() as session:
                stmt = delete(PronunciationRule).where(
                    PronunciationRule.word == word.lower()
                )
                result = await session.execute(stmt)
                await session.commit()
            self.invalidate_pronunciation_cache()
            return result.rowcount > 0
        except Exception:
            logger.exception("Failed to remove pronunciation rule")
            return False

    async def list_pronunciations(self) -> list[tuple[str, str]]:
        """List all pronunciation rules."""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(PronunciationRule).order_by(PronunciationRule.word)
                )
                return [(r.word, r.replacement) for r in result.scalars().all()]
        except Exception:
            logger.exception("Failed to list pronunciation rules")
            return []

    async def synthesize(self, text: str, voice: str = "") -> tuple[bytes, int]:
        """Synthesize speech using OpenAI TTS API. Returns (mp3_bytes, char_count)."""
        voice_name = voice or self.default_voice

        # Full TTS pipeline: normalize → yofikate → stress → overrides
        text = await self.pipeline.process(text)

        # Truncate very long text (OpenAI TTS limit ~4096 chars)
        if len(text) > 4000:
            text = text[:4000] + "..."

        char_count = len(text)

        response = await self.openai_client.audio.speech.create(
            model=OPENAI_TTS_MODEL,
            voice=voice_name,
            input=text,
            instructions=TTS_STYLE,
            response_format="mp3",
        )
        audio_bytes = response.content
        logger.info("OpenAI TTS (%s) synthesized %d chars → %d bytes audio", voice_name, char_count, len(audio_bytes))
        return audio_bytes, char_count
