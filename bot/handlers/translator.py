"""Translator mode handler: RU ↔ AR translation."""

import logging

from aiogram import Router, F, Bot
from aiogram.filters import Filter, Command
from aiogram.types import Message, BufferedInputFile

from bot.keyboards.main_menu import get_main_menu
from bot.keyboards.translator import get_translator_menu
from bot.services.ai_router import AIRouter, PROVIDERS
from bot.services.balance_service import BalanceService
from bot.services.file_service import FileService
from bot.services.translator_service import TranslatorService
from bot.services.voice_service import VoiceService
from bot.utils.formatting import md_to_html
from bot.utils.prompts import TRANSLATOR_SYSTEM_PROMPT, TRANSLATOR_QUESTION_PROMPT

logger = logging.getLogger(__name__)
router = Router()

# ── In-memory state per user ──
_translator_state: dict[int, dict] = {}

# Default translator provider
DEFAULT_TRANSLATOR_PROVIDER = "claude"


class TranslatorActive(Filter):
    """Filter: passes only when user is in translator mode."""
    async def __call__(self, message: Message) -> bool:
        return _translator_state.get(message.from_user.id, {}).get("active", False)


class WaitingPromptText(Filter):
    """Filter: passes when user is waiting to send prompt text."""
    async def __call__(self, message: Message) -> bool:
        state = _translator_state.get(message.from_user.id, {})
        return state.get("active", False) and state.get("waiting_prompt_name") is not None


class PromptButton(Filter):
    """Filter: matches prompt switching buttons."""
    async def __call__(self, message: Message) -> bool:
        if not message.text:
            return False
        return message.text.startswith("\u00b7 ") or message.text.startswith("\u2713 ")


def _get_state(user_id: int) -> dict:
    if user_id not in _translator_state:
        _translator_state[user_id] = {
            "active": False,
            "direction": "auto",
            "waiting_prompt_name": None,
            "last_source": None,
            "last_translation": None,
            "last_provider": None,
            "last_system_prompt": None,
            "last_prompt_id": None,
        }
    return _translator_state[user_id]


def _direction_label(direction: str) -> str:
    if direction == "ru_ar":
        return "RU\u2192AR"
    elif direction == "ar_ru":
        return "AR\u2192RU"
    return "Авто"


async def _get_translator_keyboard(user_id: int, translator_service: TranslatorService):
    """Build translator keyboard with prompt buttons."""
    prompts = await translator_service.get_prompts(user_id)
    if not prompts:
        return get_translator_menu()
    prompt_names = [p.name for p in prompts]
    active = next((p.name for p in prompts if p.is_active), None)
    return get_translator_menu(prompt_names=prompt_names, active_prompt=active)


async def _get_active_prompt_info(
    user_id: int, translator_service: TranslatorService,
) -> tuple[str, int | None]:
    """Get (system_prompt, prompt_id) — active custom or standard."""
    active = await translator_service.get_active_prompt(user_id)
    if active:
        return active.system_prompt, active.id
    return TRANSLATOR_SYSTEM_PROMPT, None


# ═══════════════════════════════════════════════════════
#  ENTER / EXIT TRANSLATOR MODE
# ═══════════════════════════════════════════════════════

@router.message(F.text == "Переводчик")
async def enter_translator(message: Message, translator_service: TranslatorService):
    state = _get_state(message.from_user.id)
    state["active"] = True
    state["direction"] = "auto"
    state["waiting_prompt_name"] = None
    state["last_source"] = None
    state["last_translation"] = None
    state["last_provider"] = None

    keyboard = await _get_translator_keyboard(message.from_user.id, translator_service)
    active = await translator_service.get_active_prompt(message.from_user.id)
    prompt_info = f"\nПромпт: {active.name}" if active else ""

    await message.answer(
        "<b>Режим переводчика</b> (русский \u2194 арабский)\n\n"
        "Отправьте текст, голосовое, фото или документ для перевода.\n"
        f"Направление: Авто{prompt_info}\n\n"
        "Команды:\n"
        "/glossary \u2014 управление глоссарием\n"
        "/translator_prompt \u2014 кастомные промпты",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


@router.message(TranslatorActive(), F.text == "Вернуться в чат")
async def exit_translator(message: Message):
    state = _get_state(message.from_user.id)
    state["active"] = False
    state["waiting_prompt_name"] = None
    await message.answer(
        "Режим переводчика выключен",
        reply_markup=get_main_menu(),
    )


# ═══════════════════════════════════════════════════════
#  DIRECTION BUTTONS
# ═══════════════════════════════════════════════════════

@router.message(TranslatorActive(), F.text == "Рус \u2192 Араб")
async def set_ru_ar(message: Message):
    state = _get_state(message.from_user.id)
    state["direction"] = "ru_ar"
    await message.answer("Направление: русский \u2192 арабский")


@router.message(TranslatorActive(), F.text == "Араб \u2192 Рус")
async def set_ar_ru(message: Message):
    state = _get_state(message.from_user.id)
    state["direction"] = "ar_ru"
    await message.answer("Направление: арабский \u2192 русский")


@router.message(TranslatorActive(), F.text == "Авто")
async def set_auto(message: Message):
    state = _get_state(message.from_user.id)
    state["direction"] = "auto"
    await message.answer("Направление: автоопределение")


# ═══════════════════════════════════════════════════════
#  COMPARE MODE
# ═══════════════════════════════════════════════════════

@router.message(TranslatorActive(), F.text == "Сравнить 3 модели")
async def compare_models(
    message: Message,
    translator_service: TranslatorService,
    ai_router: AIRouter,
    balance_service: BalanceService,
):
    user_id = message.from_user.id
    state = _get_state(user_id)

    if not state.get("last_source") or not state.get("last_translation"):
        await message.answer("Сначала отправьте текст для перевода.")
        return

    source = state["last_source"]
    existing_translation = state["last_translation"]
    existing_provider = state["last_provider"]
    system_prompt = state.get("last_system_prompt") or TRANSLATOR_SYSTEM_PROMPT
    prompt_id = state.get("last_prompt_id")
    direction = state["direction"]

    waiting = await message.answer("Перевожу оставшимися 2 моделями...")

    try:
        remaining = await translator_service.translate_remaining(
            source, direction, system_prompt,
            exclude_provider=existing_provider,
            prompt_id=prompt_id,
        )

        # Build all 3 results: existing first, then remaining
        all_results = {existing_provider: existing_translation}
        all_results.update(remaining)

        parts = []
        for provider, translation in all_results.items():
            info = PROVIDERS.get(provider, {})
            display = info.get("display", provider)
            parts.append(f"<b>{display}:</b>\n{translation}")

            # Track usage for new translations only
            if provider != existing_provider:
                service = ai_router.get_service(provider)
                if balance_service and service.last_usage:
                    await balance_service.track_ai_usage(
                        provider,
                        service.last_usage["input_tokens"],
                        service.last_usage["output_tokens"],
                    )

        result_text = "\n\n\u2501\u2501\u2501\n\n".join(parts)
        if len(result_text) <= 4000:
            await waiting.edit_text(result_text, parse_mode="HTML")
        else:
            await waiting.delete()
            for part in parts:
                await message.answer(part, parse_mode="HTML")

    except Exception as e:
        logger.exception("Compare translation failed")
        await waiting.edit_text(f"Ошибка сравнения: {str(e)[:300]}")


# ═══════════════════════════════════════════════════════
#  GLOSSARY BUTTON + COMMAND
# ═══════════════════════════════════════════════════════

@router.message(TranslatorActive(), F.text == "Глоссарий")
async def glossary_button(message: Message, translator_service: TranslatorService):
    await _show_glossary(message, translator_service)


@router.message(Command("glossary"))
async def glossary_command(message: Message, translator_service: TranslatorService):
    args = message.text.strip().split(maxsplit=1)
    if len(args) < 2 or args[1].strip().lower() == "list":
        await _show_glossary(message, translator_service)
        return

    sub = args[1].strip()

    # /glossary add термин = перевод
    if sub.lower().startswith("add "):
        rest = sub[4:].strip()
        if "=" not in rest:
            await message.answer("Формат: /glossary add термин = перевод")
            return
        term_ru, term_ar = rest.split("=", 1)
        term_ru = term_ru.strip()
        term_ar = term_ar.strip()
        if not term_ru or not term_ar:
            await message.answer("Формат: /glossary add термин = перевод")
            return
        # Tie to active prompt if any
        active = await translator_service.get_active_prompt(message.from_user.id)
        prompt_id = active.id if active else None
        ok = await translator_service.add_glossary(term_ru, term_ar, prompt_id=prompt_id)
        if ok:
            scope = f" (промпт: {active.name})" if active else " (глобальный)"
            await message.answer(
                f"Добавлено: <b>{term_ru}</b> = {term_ar}{scope}",
                parse_mode="HTML",
            )
        else:
            await message.answer("Ошибка при добавлении")
        return

    # /glossary remove термин
    if sub.lower().startswith("remove "):
        term = sub[7:].strip()
        if not term:
            await message.answer("Формат: /glossary remove термин")
            return
        ok = await translator_service.remove_glossary(term)
        if ok:
            await message.answer(f"Удалено: {term}")
        else:
            await message.answer(f"Термин «{term}» не найден")
        return

    await message.answer(
        "Команды глоссария:\n"
        "• /glossary — список\n"
        "• /glossary add термин = перевод\n"
        "• /glossary remove термин"
    )


async def _show_glossary(message: Message, translator_service: TranslatorService):
    active = await translator_service.get_active_prompt(message.from_user.id)
    prompt_id = active.id if active else None
    entries = await translator_service.get_glossary(prompt_id=prompt_id)
    if not entries:
        await message.answer(
            "Глоссарий пуст.\n\n"
            "Добавьте: /glossary add термин = перевод"
        )
        return

    lines = [f"\u2022 <b>{ru}</b> = {ar}" for ru, ar in entries]
    header = "<b>Глоссарий</b>"
    if active:
        header += f" (промпт: {active.name})"
    text = header + "\n\n" + "\n".join(lines)
    await message.answer(text, parse_mode="HTML")


# ═══════════════════════════════════════════════════════
#  CUSTOM PROMPTS
# ═══════════════════════════════════════════════════════

@router.message(Command("translator_prompt"))
async def cmd_translator_prompt(message: Message, translator_service: TranslatorService):
    args = message.text.strip().split(maxsplit=2)
    user_id = message.from_user.id

    if len(args) < 2 or args[1].lower() == "list":
        prompts = await translator_service.get_prompts(user_id)
        if not prompts:
            await message.answer(
                "<b>Кастомные промпты</b>\n\n"
                "Нет промптов.\n\n"
                "Добавить: <code>/translator_prompt add название</code>\n"
                "Затем отправьте текст промпта.",
                parse_mode="HTML",
            )
            return
        lines = ["<b>Кастомные промпты</b>\n"]
        for p in prompts:
            status = "\u2713" if p.is_active else "\u00b7"
            lines.append(f"{status} <b>{p.name}</b> ({len(p.system_prompt)} символов)")
        lines.append("")
        lines.append("Активировать: <code>/translator_prompt activate название</code>")
        lines.append("Выключить: <code>/translator_prompt off</code>")
        lines.append("Удалить: <code>/translator_prompt delete название</code>")
        await message.answer("\n".join(lines), parse_mode="HTML")
        return

    sub = args[1].lower()

    if sub == "add":
        if len(args) < 3:
            await message.answer(
                "Формат: <code>/translator_prompt add название</code>",
                parse_mode="HTML",
            )
            return
        name = args[2].strip()
        state = _get_state(user_id)
        state["waiting_prompt_name"] = name
        await message.answer(
            f"Промпт <b>\u00ab{name}\u00bb</b>\n\n"
            "Теперь отправьте текст системного промпта.",
            parse_mode="HTML",
        )
        return

    if sub == "activate":
        if len(args) < 3:
            await message.answer(
                "Формат: <code>/translator_prompt activate название</code>",
                parse_mode="HTML",
            )
            return
        name = args[2].strip()
        ok = await translator_service.activate_prompt(user_id, name)
        if ok:
            keyboard = await _get_translator_keyboard(user_id, translator_service)
            await message.answer(
                f"Промпт <b>\u00ab{name}\u00bb</b> активирован",
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        else:
            await message.answer(f"Промпт «{name}» не найден")
        return

    if sub == "off":
        await translator_service.deactivate_all_prompts(user_id)
        keyboard = await _get_translator_keyboard(user_id, translator_service)
        await message.answer(
            "Стандартный промпт восстановлен",
            reply_markup=keyboard,
        )
        return

    if sub == "delete":
        if len(args) < 3:
            await message.answer(
                "Формат: <code>/translator_prompt delete название</code>",
                parse_mode="HTML",
            )
            return
        name = args[2].strip()
        ok = await translator_service.delete_prompt(user_id, name)
        if ok:
            keyboard = await _get_translator_keyboard(user_id, translator_service)
            await message.answer(
                f"Промпт <b>\u00ab{name}\u00bb</b> удалён",
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        else:
            await message.answer(f"Промпт «{name}» не найден")
        return

    await message.answer(
        "Команды:\n"
        "• <code>/translator_prompt list</code> — список\n"
        "• <code>/translator_prompt add название</code> — добавить\n"
        "• <code>/translator_prompt activate название</code> — активировать\n"
        "• <code>/translator_prompt off</code> — стандартный промпт\n"
        "• <code>/translator_prompt delete название</code> — удалить",
        parse_mode="HTML",
    )


# ═══════════════════════════════════════════════════════
#  PROMPT TEXT INPUT (waiting for prompt body)
# ═══════════════════════════════════════════════════════

@router.message(WaitingPromptText(), F.text)
async def handle_prompt_text(message: Message, translator_service: TranslatorService):
    user_id = message.from_user.id
    state = _get_state(user_id)
    name = state["waiting_prompt_name"]
    state["waiting_prompt_name"] = None

    prompt_text = message.text.strip()
    prompt_id = await translator_service.add_prompt(user_id, name, prompt_text)

    if prompt_id:
        keyboard = await _get_translator_keyboard(user_id, translator_service)
        await message.answer(
            f"Промпт <b>\u00ab{name}\u00bb</b> сохранён ({len(prompt_text)} символов)\n\n"
            f"Активировать: <code>/translator_prompt activate {name}</code>",
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    else:
        await message.answer("Ошибка сохранения промпта")


# ═══════════════════════════════════════════════════════
#  PROMPT SWITCHING BUTTONS
# ═══════════════════════════════════════════════════════

@router.message(TranslatorActive(), PromptButton())
async def handle_prompt_button(message: Message, translator_service: TranslatorService):
    user_id = message.from_user.id
    # Strip prefix (·/✓ + space = 2 chars)
    name = message.text[2:].strip()

    if name == "Стандарт":
        await translator_service.deactivate_all_prompts(user_id)
    else:
        ok = await translator_service.activate_prompt(user_id, name)
        if not ok:
            await message.answer(f"Промпт «{name}» не найден")
            return

    keyboard = await _get_translator_keyboard(user_id, translator_service)
    active = await translator_service.get_active_prompt(user_id)
    if active:
        await message.answer(
            f"Промпт: <b>{active.name}</b>",
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    else:
        await message.answer("Стандартный промпт", reply_markup=keyboard)


# ═══════════════════════════════════════════════════════
#  TEXT TRANSLATION
# ═══════════════════════════════════════════════════════

@router.message(TranslatorActive(), F.text)
async def handle_translator_text(
    message: Message,
    translator_service: TranslatorService,
    ai_router: AIRouter,
    balance_service: BalanceService,
):
    user_id = message.from_user.id
    text = message.text.strip()
    state = _get_state(user_id)

    # Check if it's a question about translation
    if translator_service.is_question(text):
        waiting = await message.answer("Отвечаю...")
        provider = DEFAULT_TRANSLATOR_PROVIDER
        service = ai_router.get_service(provider)
        messages = [{"role": "user", "content": text}]
        try:
            result = await service.generate(messages, system_prompt=TRANSLATOR_QUESTION_PROMPT)
            html = md_to_html(result)
            if len(html) <= 4000:
                await waiting.edit_text(html, parse_mode="HTML")
            else:
                await waiting.edit_text(html[:4000] + "...", parse_mode="HTML")

            if balance_service and service.last_usage:
                await balance_service.track_ai_usage(
                    provider, service.last_usage["input_tokens"], service.last_usage["output_tokens"]
                )
        except Exception as e:
            await waiting.edit_text(f"Ошибка: {str(e)[:300]}")
        return

    # Get active prompt
    system_prompt, prompt_id = await _get_active_prompt_info(user_id, translator_service)

    # Normal translation
    direction = state["direction"]
    dir_label = _direction_label(direction)
    waiting = await message.answer(f"{dir_label} Перевожу...")

    try:
        translation, provider = await translator_service.translate(
            text, direction, system_prompt,
            provider=DEFAULT_TRANSLATOR_PROVIDER,
            prompt_id=prompt_id,
        )
        await waiting.edit_text(translation)

        # Save for compare button
        state["last_source"] = text
        state["last_translation"] = translation
        state["last_provider"] = provider
        state["last_system_prompt"] = system_prompt
        state["last_prompt_id"] = prompt_id

        # Track usage
        service = ai_router.get_service(provider)
        if balance_service and service.last_usage:
            await balance_service.track_ai_usage(
                provider, service.last_usage["input_tokens"], service.last_usage["output_tokens"]
            )

    except Exception as e:
        logger.exception("Translation failed")
        await waiting.edit_text(f"Ошибка перевода: {str(e)[:300]}")


# ═══════════════════════════════════════════════════════
#  VOICE TRANSLATION
# ═══════════════════════════════════════════════════════

@router.message(TranslatorActive(), F.voice)
async def handle_translator_voice(
    message: Message,
    bot: Bot,
    translator_service: TranslatorService,
    ai_router: AIRouter,
    voice_service: VoiceService,
    balance_service: BalanceService,
):
    user_id = message.from_user.id
    state = _get_state(user_id)

    # Download and transcribe
    voice = message.voice
    file = await bot.get_file(voice.file_id)
    file_bytes = await bot.download_file(file.file_path)
    audio_data = file_bytes.read()

    waiting = await message.answer("Распознаю речь...")

    try:
        text = await voice_service.transcribe(audio_data)
        if balance_service and voice.duration:
            await balance_service.track_whisper(voice.duration)
    except Exception as e:
        await waiting.edit_text(f"Ошибка распознавания: {str(e)[:200]}")
        return

    if not text:
        await waiting.edit_text("Не удалось распознать речь")
        return

    # Get active prompt
    system_prompt, prompt_id = await _get_active_prompt_info(user_id, translator_service)

    # Show transcription
    direction = state["direction"]
    dir_label = _direction_label(direction)
    await waiting.edit_text(
        f"<b>Распознано:</b> {text}\n\n{dir_label} Перевожу...",
        parse_mode="HTML",
    )

    try:
        translation, provider = await translator_service.translate(
            text, direction, system_prompt,
            provider=DEFAULT_TRANSLATOR_PROVIDER,
            prompt_id=prompt_id,
        )

        await waiting.edit_text(
            f"<b>Распознано:</b> {text}\n\n"
            f"<b>Перевод:</b>\n{translation}",
            parse_mode="HTML",
        )

        # Track AI usage
        service = ai_router.get_service(provider)
        if balance_service and service.last_usage:
            await balance_service.track_ai_usage(
                provider, service.last_usage["input_tokens"], service.last_usage["output_tokens"]
            )

        # TTS the translation
        try:
            voice_name = voice_service.get_voice(provider)
            audio_bytes, char_count = await voice_service.synthesize(translation, voice=voice_name)
            voice_file = BufferedInputFile(audio_bytes, filename="translation.mp3")
            await message.answer_voice(voice_file)
            if balance_service:
                await balance_service.track_tts(char_count)
        except Exception as e:
            logger.exception("Translation TTS failed")

    except Exception as e:
        logger.exception("Voice translation failed")
        await waiting.edit_text(f"Ошибка перевода: {str(e)[:300]}")


# ═══════════════════════════════════════════════════════
#  PHOTO TRANSLATION (Vision API)
# ═══════════════════════════════════════════════════════

@router.message(TranslatorActive(), F.photo)
async def handle_translator_photo(
    message: Message,
    bot: Bot,
    translator_service: TranslatorService,
    ai_router: AIRouter,
    balance_service: BalanceService,
):
    user_id = message.from_user.id
    state = _get_state(user_id)
    direction = state["direction"]

    # Download photo
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    image_data = file_bytes.read()

    waiting = await message.answer("Распознаю текст на фото...")

    provider = DEFAULT_TRANSLATOR_PROVIDER
    service = ai_router.get_service(provider)

    # Step 1: Extract text from image via Vision API
    extract_prompt = (
        "Извлеки ВЕСЬ текст с этого изображения. "
        "Верни только текст, без описания изображения. "
        "Сохрани форматирование (абзацы, списки)."
    )
    try:
        extracted = await service.generate_with_image(
            image_data, "image/jpeg", extract_prompt,
        )
    except Exception as e:
        await waiting.edit_text(f"Ошибка Vision API: {str(e)[:300]}")
        return

    if not extracted or len(extracted.strip()) < 2:
        await waiting.edit_text("Не удалось распознать текст на изображении")
        return

    # Track Vision usage
    if balance_service and service.last_usage:
        await balance_service.track_ai_usage(
            provider, service.last_usage["input_tokens"], service.last_usage["output_tokens"]
        )

    # Get active prompt
    system_prompt, prompt_id = await _get_active_prompt_info(user_id, translator_service)

    # Step 2: Translate extracted text
    dir_label = _direction_label(direction)
    await waiting.edit_text(
        f"<b>Распознано:</b>\n{extracted[:500]}\n\n{dir_label} Перевожу...",
        parse_mode="HTML",
    )

    try:
        translation, provider = await translator_service.translate(
            extracted, direction, system_prompt,
            provider=DEFAULT_TRANSLATOR_PROVIDER,
            prompt_id=prompt_id,
        )
        await waiting.edit_text(
            f"<b>Текст с фото:</b>\n{extracted[:500]}\n\n"
            f"<b>Перевод:</b>\n{translation}",
            parse_mode="HTML",
        )

        service = ai_router.get_service(provider)
        if balance_service and service.last_usage:
            await balance_service.track_ai_usage(
                provider, service.last_usage["input_tokens"], service.last_usage["output_tokens"]
            )

    except Exception as e:
        await waiting.edit_text(f"Ошибка перевода: {str(e)[:300]}")


# ═══════════════════════════════════════════════════════
#  DOCUMENT TRANSLATION
# ═══════════════════════════════════════════════════════

@router.message(TranslatorActive(), F.document)
async def handle_translator_document(
    message: Message,
    bot: Bot,
    translator_service: TranslatorService,
    ai_router: AIRouter,
    file_service: FileService,
    balance_service: BalanceService,
):
    user_id = message.from_user.id
    state = _get_state(user_id)
    direction = state["direction"]

    doc = message.document
    filename = doc.file_name or "document"

    # Check file type
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in (".pdf", ".docx", ".txt", ".csv"):
        await message.answer(
            "Поддерживаемые форматы: PDF, DOCX, TXT, CSV"
        )
        return

    waiting = await message.answer(f"Обрабатываю {filename}...")

    # Download file
    file = await bot.get_file(doc.file_id)
    file_bytes = await bot.download_file(file.file_path)
    data = file_bytes.read()

    # Save and extract text via FileService
    project_file = await file_service.save_file(user_id, filename, data)
    if not project_file or not project_file.extracted_text:
        await waiting.edit_text("Не удалось извлечь текст из документа")
        return

    extracted = project_file.extracted_text
    dir_label = _direction_label(direction)

    # Limit: translate first 4000 chars (AI context limit)
    if len(extracted) > 4000:
        extracted_for_translation = extracted[:4000]
        truncated = True
    else:
        extracted_for_translation = extracted
        truncated = False

    await waiting.edit_text(
        f"Извлечено {len(extracted)} символов из {filename}\n"
        f"{dir_label} Перевожу...",
    )

    # Get active prompt
    system_prompt, prompt_id = await _get_active_prompt_info(user_id, translator_service)

    try:
        translation, provider = await translator_service.translate(
            extracted_for_translation, direction, system_prompt,
            provider=DEFAULT_TRANSLATOR_PROVIDER,
            prompt_id=prompt_id,
        )

        result_text = f"<b>{filename}</b>\n\n<b>Перевод:</b>\n{translation}"
        if truncated:
            result_text += f"\n\nПереведены первые 4000 из {len(extracted)} символов"

        if len(result_text) <= 4000:
            await waiting.edit_text(result_text, parse_mode="HTML")
        else:
            await waiting.delete()
            # Split into chunks
            for i in range(0, len(result_text), 4000):
                chunk = result_text[i:i + 4000]
                await message.answer(chunk, parse_mode="HTML")

        service = ai_router.get_service(provider)
        if balance_service and service.last_usage:
            await balance_service.track_ai_usage(
                provider, service.last_usage["input_tokens"], service.last_usage["output_tokens"]
            )

    except Exception as e:
        await waiting.edit_text(f"Ошибка перевода документа: {str(e)[:300]}")
