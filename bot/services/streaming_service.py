import logging
import time
from collections.abc import AsyncGenerator
from datetime import datetime

from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

from bot.utils.formatting import md_to_html

logger = logging.getLogger(__name__)

MAX_TG_MESSAGE = 4096
TELEGRAPH_THRESHOLD = 3800  # publish to Telegraph if text exceeds this
CURSOR = " \u258c"  # ▌


def _make_signature(model_label: str, balance_str: str = "") -> str:
    """Build HTML signature wrapped in blockquote."""
    date = datetime.now().strftime("%d.%m.%Y")
    parts = [model_label, date]
    if balance_str:
        parts.append(balance_str)
    return f'\n\n<blockquote>\u2014 {" | ".join(parts)}</blockquote>'


async def _send_html_with_sig(
    msg: Message,
    text: str,
    signature: str = "",
    edit: bool = False,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    """Convert text to HTML, append raw HTML signature, send/edit. Fallback to plain."""
    html_text = md_to_html(text) + signature
    try:
        if edit:
            await msg.edit_text(html_text, parse_mode="HTML", reply_markup=reply_markup)
        else:
            await msg.answer(html_text, parse_mode="HTML", reply_markup=reply_markup)
        return True
    except TelegramBadRequest:
        plain = text + signature.replace("<blockquote>", "").replace("</blockquote>", "")
        try:
            if edit:
                await msg.edit_text(plain, reply_markup=reply_markup)
            else:
                await msg.answer(plain, reply_markup=reply_markup)
            return True
        except TelegramBadRequest:
            return False


async def _send_html(
    msg: Message,
    text: str,
    edit: bool = False,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    return await _send_html_with_sig(msg, text, "", edit, reply_markup)


def _add_telegraph_button(
    reply_markup: InlineKeyboardMarkup | None, url: str
) -> InlineKeyboardMarkup:
    """Add 'Read full' Telegraph button to existing keyboard."""
    btn = InlineKeyboardButton(text="Читать полностью", url=url)
    if reply_markup and reply_markup.inline_keyboard:
        rows = list(reply_markup.inline_keyboard) + [[btn]]
        return InlineKeyboardMarkup(inline_keyboard=rows)
    return InlineKeyboardMarkup(inline_keyboard=[[btn]])


class StreamingService:

    @staticmethod
    async def stream_response(
        message: Message,
        generator: AsyncGenerator[str, None],
        model_display: str,
        update_interval: float = 1.0,
        reply_markup: InlineKeyboardMarkup | None = None,
        model_label: str = "",
        telegraph_service=None,
        balance_str: str = "",
    ) -> tuple[Message, str]:
        """Stream AI response into a Telegram message with live editing.

        If response > TELEGRAPH_THRESHOLD chars, publish full text to Telegraph
        and send a preview + link in Telegram.

        Returns (final_message, full_text).
        """
        bot_msg = await message.answer(f"{model_display} думает...")

        buffer = ""
        last_edit_time = time.monotonic()
        last_sent_text = ""

        try:
            async for token in generator:
                buffer += token
                now = time.monotonic()

                if now - last_edit_time >= update_interval:
                    display = buffer
                    if len(display) > MAX_TG_MESSAGE - 5:
                        display = display[: MAX_TG_MESSAGE - 5]
                    display += CURSOR

                    if display != last_sent_text:
                        try:
                            await bot_msg.edit_text(display)
                            last_sent_text = display
                        except TelegramBadRequest:
                            pass
                        last_edit_time = now

            # Final send with HTML formatting
            if not buffer:
                await bot_msg.edit_text(
                    f"{model_display} вернул пустой ответ"
                )
                return bot_msg, ""

            signature = _make_signature(model_label, balance_str) if model_label else ""

            if len(buffer) <= TELEGRAPH_THRESHOLD:
                # Short enough for inline message
                await _send_html_with_sig(
                    bot_msg, buffer, signature, edit=True, reply_markup=reply_markup
                )
            elif telegraph_service:
                # Long response → publish to Telegraph
                date = datetime.now().strftime("%d.%m.%Y")
                title = f"{model_label} | {date}"
                url = await telegraph_service.publish(title, buffer, author=model_label)

                if url:
                    # Send preview (first ~800 chars) + link
                    preview = buffer[:800].rsplit("\n", 1)[0] + "\n..."
                    markup = _add_telegraph_button(reply_markup, url)
                    await _send_html_with_sig(
                        bot_msg, preview, signature, edit=True, reply_markup=markup
                    )
                else:
                    # Telegraph failed — fallback to split
                    await _send_split(bot_msg, message, buffer, signature, reply_markup)
            else:
                # No telegraph — split into messages
                await _send_split(bot_msg, message, buffer, signature, reply_markup)

        except Exception as e:
            error_text = f"Ошибка {model_display}: {str(e)[:500]}"
            logger.exception("Streaming error for %s", model_display)
            try:
                await bot_msg.edit_text(error_text)
            except Exception:
                bot_msg = await message.answer(error_text)
            return bot_msg, ""

        return bot_msg, buffer


async def _send_split(
    bot_msg: Message,
    original_message: Message,
    buffer: str,
    signature: str,
    reply_markup: InlineKeyboardMarkup | None,
):
    """Fallback: split long text into multiple messages."""
    chunks = _split_text(buffer, 3000)
    await _send_html(bot_msg, chunks[0], edit=True)
    for i, chunk in enumerate(chunks[1:], 1):
        is_last = i == len(chunks) - 1
        markup = reply_markup if is_last else None
        sig = signature if is_last else ""
        bot_msg = await _send_html_new(original_message, chunk, sig, reply_markup=markup)


async def _send_html_new(
    message: Message,
    text: str,
    signature: str = "",
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message:
    html_text = md_to_html(text) + signature
    try:
        return await message.answer(html_text, parse_mode="HTML", reply_markup=reply_markup)
    except TelegramBadRequest:
        plain = text + signature.replace("<blockquote>", "").replace("</blockquote>", "")
        return await message.answer(plain, reply_markup=reply_markup)


def _split_text(text: str, max_len: int) -> list[str]:
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, max_len)
        if split_at < max_len // 2:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks
