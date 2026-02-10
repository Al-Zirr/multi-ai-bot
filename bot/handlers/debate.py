import json
import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.services.ai_router import AIRouter
from bot.services.debate_service import DebateService
from bot.services.streaming_service import _split_text
from bot.utils.formatting import md_to_html

logger = logging.getLogger(__name__)
router = Router()

# In-memory debate state per user
_debate_state: dict[int, dict] = {}

MAX_TG = 4096


def _debate_keyboard(has_debate: bool = False) -> InlineKeyboardMarkup:
    if has_debate:
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подвести итог",
                    callback_data="debate:summary",
                ),
                InlineKeyboardButton(
                    text="Ещё раунд",
                    callback_data="debate:another",
                ),
            ]
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Запустить дебаты",
                callback_data="debate:start",
            ),
        ]
    ])


async def _send_long(message: Message, text: str, reply_markup=None):
    """Send text as HTML, splitting if needed. Markup goes on last chunk."""
    from aiogram.exceptions import TelegramBadRequest

    html_text = md_to_html(text)
    if len(html_text) <= MAX_TG:
        try:
            await message.answer(html_text, parse_mode="HTML", reply_markup=reply_markup)
        except TelegramBadRequest:
            await message.answer(text, reply_markup=reply_markup)
    else:
        chunks = _split_text(text, 3000)
        for i, chunk in enumerate(chunks):
            markup = reply_markup if i == len(chunks) - 1 else None
            chunk_html = md_to_html(chunk)
            try:
                await message.answer(chunk_html, parse_mode="HTML", reply_markup=markup)
            except TelegramBadRequest:
                await message.answer(chunk, reply_markup=markup)


@router.callback_query(F.data == "debate:start")
async def on_debate_start(callback: CallbackQuery, ai_router: AIRouter):
    user_id = callback.from_user.id
    state = _debate_state.get(user_id)

    if not state or "answers" not in state:
        await callback.answer(
            "Нет данных для дебатов",
            show_alert=True,
        )
        return

    await callback.answer("Запускаю дебаты...")

    waiting = await callback.message.answer(
        "Модели анализируют ответы друг друга..."
    )

    debate_svc = DebateService(ai_router)
    critiques = await debate_svc.run_debate_round(state["question"], state["answers"])
    state["critiques"] = critiques

    await waiting.delete()

    debate_text = debate_svc.format_debate(critiques)
    await _send_long(
        callback.message, debate_text, reply_markup=_debate_keyboard(has_debate=True)
    )


@router.callback_query(F.data == "debate:another")
async def on_debate_another(callback: CallbackQuery, ai_router: AIRouter):
    user_id = callback.from_user.id
    state = _debate_state.get(user_id)

    if not state or "critiques" not in state:
        await callback.answer("Нет данных", show_alert=True)
        return

    await callback.answer("Ещё раунд...")

    waiting = await callback.message.answer(
        "Модели продолжают дискуссию..."
    )

    # Use critiques as new "answers" for next round
    debate_svc = DebateService(ai_router)
    critiques = await debate_svc.run_debate_round(state["question"], state["critiques"])
    state["critiques"] = critiques

    await waiting.delete()

    debate_text = debate_svc.format_debate(critiques)
    await _send_long(
        callback.message, debate_text, reply_markup=_debate_keyboard(has_debate=True)
    )


@router.callback_query(F.data == "debate:summary")
async def on_debate_summary(callback: CallbackQuery, ai_router: AIRouter):
    user_id = callback.from_user.id
    state = _debate_state.get(user_id)

    if not state:
        await callback.answer("Нет данных", show_alert=True)
        return

    await callback.answer("Подвожу итог...")

    waiting = await callback.message.answer(
        "Готовлю финальное резюме..."
    )

    debate_svc = DebateService(ai_router)
    summary = await debate_svc.summarize(
        state["question"],
        state.get("answers", {}),
        state.get("critiques", {}),
    )

    await waiting.delete()

    summary_text = f"Итог дебатов\n\n{summary}"
    await _send_long(callback.message, summary_text)

    # Clean up state
    _debate_state.pop(user_id, None)


def save_debate_state(user_id: int, question: str, answers: dict):
    """Called from chat handler after 'ask all' to enable debates."""
    _debate_state[user_id] = {
        "question": question,
        "answers": answers,
    }
