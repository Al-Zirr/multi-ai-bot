"""Voice message handler: STT + optional TTS."""

import logging
import re
from io import BytesIO

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile

from bot.config import Config
from bot.keyboards.model_select import get_response_keyboard
from bot.services.ai_router import AIRouter
from bot.services.context_service import ContextService
from bot.services.file_service import FileService
from bot.services.rag_service import RAGService
from bot.services.search_service import SearchService
from bot.services.balance_service import BalanceService
from bot.services.settings_service import SettingsService
from bot.services.streaming_service import StreamingService
from bot.services.telegraph_service import TelegraphService
from bot.services.quota_service import QuotaService
from bot.services.voice_service import VoiceService
from bot.utils.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)
router = Router()

# "озвучь мой текст" / "прочитай" → direct TTS (no AI)
_TTS_DIRECT_PATTERN = re.compile(
    r"\b(озвучь\s+мой\s+текст|прочитай|прочти|прочитать)\b", re.IGNORECASE
)
# "озвучь" → AI response + TTS
_TTS_AI_PATTERN = re.compile(r"\b(озвучь|озвучить|озвучи)\b", re.IGNORECASE)


def _strip_tts_trigger(text: str) -> tuple[str, str]:
    """Detect TTS mode. Returns (clean_text, mode).

    mode: "" = no TTS, "ai" = AI+TTS, "direct" = TTS only (no AI).
    """
    # Check "direct" patterns first (longer match before shorter)
    if _TTS_DIRECT_PATTERN.search(text):
        clean = _TTS_DIRECT_PATTERN.sub("", text).strip()
        clean = re.sub(r"\s{2,}", " ", clean).strip()
        return clean, "direct"
    if _TTS_AI_PATTERN.search(text):
        clean = _TTS_AI_PATTERN.sub("", text).strip()
        clean = re.sub(r"\s{2,}", " ", clean).strip()
        return clean, "ai"
    return text, ""


@router.message(F.voice)
async def handle_voice(
    message: Message,
    bot: Bot,
    ai_router: AIRouter,
    config: Config,
    context_service: ContextService,
    file_service: FileService,
    rag_service: RAGService,
    search_service: SearchService,
    telegraph_service: TelegraphService,
    voice_service: VoiceService,
    balance_service: BalanceService,
    settings_service: SettingsService,
    quota_service: QuotaService,
):
    user_id = message.from_user.id

    # Check token quota
    allowed, error_msg = await quota_service.check_tokens(user_id)
    if not allowed:
        await message.answer(error_msg, parse_mode="HTML")
        return

    # Download voice file
    voice = message.voice
    file = await bot.get_file(voice.file_id)
    file_bytes = await bot.download_file(file.file_path)
    audio_data = file_bytes.read()

    # Transcribe
    waiting = await message.answer("Распознаю речь...")

    try:
        text = await voice_service.transcribe(audio_data)
        # Track Whisper usage
        if balance_service and voice.duration:
            await balance_service.track_whisper(voice.duration)
    except Exception as e:
        logger.exception("Whisper transcription failed")
        await waiting.edit_text(f"Ошибка распознавания: {str(e)[:200]}")
        return

    if not text:
        await waiting.edit_text("Не удалось распознать речь")
        return

    # Check for TTS trigger
    clean_text, tts_mode = _strip_tts_trigger(text)

    if not clean_text:
        clean_text = text

    # Show transcription
    await waiting.edit_text(f"<b>Распознано:</b> {clean_text}", parse_mode="HTML")

    provider = await ai_router.load_user_provider(user_id)
    user_settings = await settings_service.get(user_id)

    # "direct" mode: just TTS the user's text, no AI
    if tts_mode == "direct":
        if not clean_text:
            await message.answer("Нет текста для озвучки")
            return
        await _send_tts(message, clean_text, voice_service, balance_service, provider, user_voice=user_settings.tts_voice)
        return

    # Store for regeneration
    from bot.handlers.chat import _last_user_message
    _last_user_message[user_id] = clean_text

    # Process as regular text message through AI
    service = ai_router.get_service(provider)

    # Auto-search
    user_text = clean_text
    if search_service and user_settings.auto_search:
        should_search = search_service.should_search(clean_text)
        if should_search:
            search_results = await search_service.search_for_ai(clean_text)
            if search_results:
                user_text = (
                    f"\u0410\u041a\u0422\u0423\u0410\u041b\u042c\u041d\u042b\u0415 \u0414\u0410\u041d\u041d\u042b\u0415 \u0418\u0417 \u0418\u041d\u0422\u0415\u0420\u041d\u0415\u0422\u0410 (\u0438\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0439 \u0438\u0445 \u043a\u0430\u043a \u0444\u0430\u043a\u0442, "
                    f"\u043d\u0435 \u043f\u0438\u0448\u0438 \u0447\u0442\u043e \u043d\u0435 \u0438\u043c\u0435\u0435\u0448\u044c \u0434\u043e\u0441\u0442\u0443\u043f\u0430 \u043a \u0434\u0430\u043d\u043d\u044b\u043c):\n"
                    f"{search_results}\n\n"
                    f"\u0412\u043e\u043f\u0440\u043e\u0441 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f: {clean_text}\n\n"
                    f"\u0412\u0410\u0416\u041d\u041e: \u041e\u0442\u0432\u0435\u0442\u044c \u043a\u043e\u043d\u043a\u0440\u0435\u0442\u043d\u043e, \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u044f \u0434\u0430\u043d\u043d\u044b\u0435 \u0432\u044b\u0448\u0435. "
                    f"\u041d\u0435 \u043f\u0440\u0435\u0434\u043b\u0430\u0433\u0430\u0439 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044e \u0438\u0441\u043a\u0430\u0442\u044c \u0441\u0430\u043c\u043e\u043c\u0443."
                )

    # Save to context
    await context_service.add_message(user_id, "user", clean_text)
    history = await context_service.get_context_for_ai(user_id, ai_service=service)

    if user_text != clean_text and history:
        history[-1] = {"role": "user", "content": user_text}

    display = ai_router.get_display_name(provider)
    label = ai_router.get_model_label(provider)

    # Get balance for signature
    balance_str = ""
    if balance_service:
        balance_str = await balance_service.format_balance_for_signature(provider)

    # Stream response
    generator = service.generate_stream(history, system_prompt=SYSTEM_PROMPT)
    bot_msg, full_text = await StreamingService.stream_response(
        message=message,
        generator=generator,
        model_display=display,
        update_interval=config.streaming_update_interval,
        reply_markup=get_response_keyboard(provider, ai_router.model_versions()),
        model_label=label,
        telegraph_service=telegraph_service,
        balance_str=balance_str,
    )

    if full_text:
        await context_service.add_message(user_id, "assistant", full_text, model=provider)

        # Track AI token usage
        if balance_service and service.last_usage:
            await balance_service.track_ai_usage(
                provider, service.last_usage["input_tokens"], service.last_usage["output_tokens"]
            )

        # Track quota
        if quota_service and service.last_usage:
            total_tokens = service.last_usage["input_tokens"] + service.last_usage["output_tokens"]
            await quota_service.track_token_usage(user_id, total_tokens)

        # TTS if "ai" mode triggered
        if tts_mode == "ai":
            await _send_tts(message, full_text, voice_service, balance_service, provider, user_voice=user_settings.tts_voice)


async def _send_tts(message: Message, text: str, voice_service: VoiceService, balance_service: BalanceService | None = None, provider: str = "", user_voice: str = ""):
    """Synthesize and send voice message."""
    try:
        voice = user_voice or voice_service.get_voice(provider)
        audio_bytes, char_count = await voice_service.synthesize(text, voice=voice)
        voice_file = BufferedInputFile(audio_bytes, filename="response.mp3")
        await message.answer_voice(voice_file)
        if balance_service:
            await balance_service.track_tts(char_count)
    except Exception as e:
        logger.exception("TTS synthesis failed")
        await message.answer(f"Ошибка озвучки: {str(e)[:200]}")


# --- TTS callback for button ---

@router.callback_query(F.data == "tts")
async def on_tts_button(
    callback: CallbackQuery,
    ai_router: AIRouter,
    voice_service: VoiceService,
    balance_service: BalanceService,
    settings_service: SettingsService,
):
    await callback.answer("Озвучиваю...")

    # Get text from the message this button belongs to
    text = callback.message.text
    if not text:
        await callback.answer("Нет текста для озвучки", show_alert=True)
        return

    user_settings = await settings_service.get(callback.from_user.id)
    provider = await ai_router.load_user_provider(callback.from_user.id)
    await _send_tts(callback.message, text, voice_service, balance_service, provider, user_voice=user_settings.tts_voice)
