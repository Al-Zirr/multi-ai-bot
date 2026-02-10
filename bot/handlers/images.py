import logging

from aiogram import Router, F, Bot
from aiogram.types import Message

from bot.config import Config
from bot.services.ai_router import AIRouter
from bot.services.balance_service import BalanceService
from bot.services.context_service import ContextService
from bot.services.telegraph_service import TelegraphService
from bot.utils.formatting import md_to_html
from bot.utils.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)
router = Router()

DEFAULT_IMAGE_PROMPT = "Опиши это изображение подробно."

# Telegram MIME type mapping
MIME_MAP = {
    "image/jpeg": "image/jpeg",
    "image/png": "image/png",
    "image/gif": "image/gif",
    "image/webp": "image/webp",
}


@router.message(F.photo)
async def handle_photo(
    message: Message,
    bot: Bot,
    ai_router: AIRouter,
    config: Config,
    context_service: ContextService,
    telegraph_service: TelegraphService,
    balance_service: BalanceService,
):
    user_id = message.from_user.id
    prompt = message.caption or DEFAULT_IMAGE_PROMPT

    # Get largest photo
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    image_data = file_bytes.read()

    # Determine mime type (Telegram photos are always JPEG)
    mime_type = "image/jpeg"

    provider = await ai_router.load_user_provider(user_id)
    service = ai_router.get_service(provider)
    display = ai_router.get_display_name(provider)

    waiting = await message.answer(
        f"{display} анализирует изображение..."
    )

    try:
        result = await service.generate_with_image(
            image_data, mime_type, prompt, system_prompt=SYSTEM_PROMPT
        )
    except Exception as e:
        logger.exception("Vision API error")
        await waiting.edit_text(f"Ошибка Vision: {str(e)[:500]}")
        return

    if result:
        await context_service.add_message(user_id, "user", f"[Изображение] {prompt}")
        await context_service.add_message(user_id, "assistant", result, model=provider)

        from bot.services.streaming_service import (
            _make_signature, _send_html_with_sig, _split_text,
            _send_html_new, _send_split, _add_telegraph_button,
            TELEGRAPH_THRESHOLD,
        )
        label = ai_router.get_model_label(provider)
        balance_str = ""
        if balance_service:
            balance_str = await balance_service.format_balance_for_signature(provider)
        signature = _make_signature(label, balance_str)

        # Track token usage
        if balance_service and service.last_usage:
            await balance_service.track_ai_usage(
                provider, service.last_usage["input_tokens"], service.last_usage["output_tokens"]
            )
        formatted = f"{display}:\n\n{result}"
        try:
            if len(formatted) <= TELEGRAPH_THRESHOLD:
                await _send_html_with_sig(waiting, formatted, signature, edit=True)
            elif telegraph_service:
                from datetime import datetime
                date = datetime.now().strftime("%d.%m.%Y")
                title = f"{label} | {date}"
                url = await telegraph_service.publish(title, formatted, author=label)
                if url:
                    preview = formatted[:800].rsplit("\n", 1)[0] + "\n..."
                    markup = _add_telegraph_button(None, url)
                    await _send_html_with_sig(waiting, preview, signature, edit=True, reply_markup=markup)
                else:
                    await _send_split(waiting, message, formatted, signature, None)
            else:
                await _send_split(waiting, message, formatted, signature, None)
        except Exception:
            plain = formatted + "\n\n\u2014 " + label
            if len(plain) <= 4096:
                await waiting.edit_text(plain)
            else:
                await waiting.edit_text(plain[:4096])
    else:
        await waiting.edit_text(
            f"{display} не смог проанализировать изображение"
        )
