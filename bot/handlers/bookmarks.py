"""Bookmarks and export handlers."""

import logging
import re

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton

from bot.services.bookmark_service import BookmarkService, PAGE_SIZE
from bot.services.export_service import ExportService

logger = logging.getLogger(__name__)
router = Router()

# Per-user state for "add note" mode: {user_id: bookmark_id}
_note_mode: dict[int, int] = {}


# ═══════════════════════════════════════════════════════
#  EXTRACT MODEL FROM SIGNATURE
# ═══════════════════════════════════════════════════════

_SIG_RE = re.compile(r"— (.+?) \|")


def _extract_model(text: str) -> str | None:
    """Extract model label from blockquote signature like '— Claude | 10.02.2026'."""
    m = _SIG_RE.search(text)
    return m.group(1).strip() if m else None


# ═══════════════════════════════════════════════════════
#  CALLBACK: SAVE BOOKMARK
# ═══════════════════════════════════════════════════════

@router.callback_query(F.data == "bookmark")
async def on_bookmark(callback: CallbackQuery, bookmark_service: BookmarkService):
    user_id = callback.from_user.id
    msg = callback.message

    # Get text from the message the button is attached to
    text = msg.text or msg.caption or ""
    if not text:
        await callback.answer("Нет текста для сохранения", show_alert=True)
        return

    model = _extract_model(text)

    bm = await bookmark_service.add(user_id, text, model=model)
    await callback.answer("Сохранено в закладки!")

    # Offer to add a note
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить заметку", callback_data=f"bm:note:{bm.id}")],
    ])
    await msg.reply("Закладка сохранена.", reply_markup=kb)


# ═══════════════════════════════════════════════════════
#  CALLBACK: ADD NOTE
# ═══════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("bm:note:"))
async def on_add_note_start(callback: CallbackQuery):
    user_id = callback.from_user.id
    bookmark_id = int(callback.data.split(":")[2])
    _note_mode[user_id] = bookmark_id
    await callback.answer()
    await callback.message.edit_text("Отправьте текст заметки:")


@router.message(F.text, lambda m: m.from_user.id in _note_mode)
async def on_note_text(message: Message, bookmark_service: BookmarkService):
    user_id = message.from_user.id
    bookmark_id = _note_mode.pop(user_id, None)
    if bookmark_id is None:
        return

    success = await bookmark_service.add_note(bookmark_id, message.text)
    if success:
        await message.answer("Заметка добавлена к закладке.")
    else:
        await message.answer("Закладка не найдена.")


# ═══════════════════════════════════════════════════════
#  COMMAND: /bookmarks
# ═══════════════════════════════════════════════════════

@router.message(Command("bookmarks"))
async def cmd_bookmarks(message: Message, bookmark_service: BookmarkService):
    args = message.text.removeprefix("/bookmarks").strip()

    # Search mode
    if args.startswith("search "):
        query = args.removeprefix("search ").strip()
        if not query:
            await message.answer("Использование: <code>/bookmarks search запрос</code>", parse_mode="HTML")
            return
        results = await bookmark_service.search(message.from_user.id, query)
        if not results:
            await message.answer("Закладки не найдены.")
            return
        text = f"<b>Найдено: {len(results)}</b>\n\n"
        for i, bm in enumerate(results[:10], 1):
            text += _format_bookmark_item(i, bm)
        kb = _build_bookmark_list_kb(results[:10])
        await message.answer(text, parse_mode="HTML", reply_markup=kb)
        return

    # List mode
    await _send_bookmark_page(message, bookmark_service, message.from_user.id, page=0)


@router.callback_query(F.data.startswith("bm:page:"))
async def on_bookmark_page(callback: CallbackQuery, bookmark_service: BookmarkService):
    page = int(callback.data.split(":")[2])
    await callback.answer()
    await _send_bookmark_page(
        callback.message, bookmark_service, callback.from_user.id, page, edit=True
    )


async def _send_bookmark_page(
    message: Message,
    bookmark_service: BookmarkService,
    user_id: int,
    page: int,
    edit: bool = False,
):
    bookmarks, total = await bookmark_service.get_all(user_id, page=page)
    if total == 0:
        text = "У вас нет закладок."
        if edit:
            await message.edit_text(text)
        else:
            await message.answer(text)
        return

    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    text = f"<b>Закладки ({total})</b> — стр. {page + 1}/{total_pages}\n\n"

    start_num = page * PAGE_SIZE + 1
    for i, bm in enumerate(bookmarks, start_num):
        text += _format_bookmark_item(i, bm)

    rows = _build_bookmark_list_kb(bookmarks).inline_keyboard

    # Pagination row
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="← Назад", callback_data=f"bm:page:{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Далее →", callback_data=f"bm:page:{page + 1}"))
    if nav_row:
        rows.append(nav_row)

    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    if edit:
        await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=kb)


def _format_bookmark_item(num: int, bm) -> str:
    model_str = bm.model or "AI"
    date_str = bm.created_at.strftime("%d.%m.%Y") if bm.created_at else ""
    text = f"<b>{num}.</b> {model_str} | {date_str}\n"
    text += f"   {bm.preview}\n"
    if bm.note:
        text += f"   <i>Заметка: {bm.note}</i>\n"
    text += "\n"
    return text


def _build_bookmark_list_kb(bookmarks) -> InlineKeyboardMarkup:
    rows = []
    for bm in bookmarks:
        rows.append([
            InlineKeyboardButton(text="Показать", callback_data=f"bm:show:{bm.id}"),
            InlineKeyboardButton(text="Удалить", callback_data=f"bm:del:{bm.id}"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ═══════════════════════════════════════════════════════
#  CALLBACK: SHOW / DELETE
# ═══════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("bm:show:"))
async def on_show_bookmark(callback: CallbackQuery, bookmark_service: BookmarkService):
    bookmark_id = int(callback.data.split(":")[2])
    bm = await bookmark_service.get_by_id(bookmark_id)
    if not bm:
        await callback.answer("Закладка не найдена", show_alert=True)
        return
    await callback.answer()

    text = bm.message_text
    if bm.note:
        text += f"\n\n<i>Заметка: {bm.note}</i>"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Добавить заметку", callback_data=f"bm:note:{bm.id}"),
            InlineKeyboardButton(text="Удалить", callback_data=f"bm:del:{bm.id}"),
        ],
        [InlineKeyboardButton(text="← К списку", callback_data="bm:back")],
    ])

    # Telegram message limit
    if len(text) > 4000:
        text = text[:4000] + "..."

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("bm:del:"))
async def on_delete_bookmark(callback: CallbackQuery, bookmark_service: BookmarkService):
    bookmark_id = int(callback.data.split(":")[2])
    await bookmark_service.delete(bookmark_id)
    await callback.answer("Закладка удалена")
    # Refresh list
    await _send_bookmark_page(
        callback.message, bookmark_service, callback.from_user.id, page=0, edit=True
    )


@router.callback_query(F.data == "bm:back")
async def on_back_to_list(callback: CallbackQuery, bookmark_service: BookmarkService):
    await callback.answer()
    await _send_bookmark_page(
        callback.message, bookmark_service, callback.from_user.id, page=0, edit=True
    )


# ═══════════════════════════════════════════════════════
#  COMMAND: /export
# ═══════════════════════════════════════════════════════

@router.message(Command("export"))
async def cmd_export(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Markdown", callback_data="export:md"),
            InlineKeyboardButton(text="JSON", callback_data="export:json"),
            InlineKeyboardButton(text="PDF", callback_data="export:pdf"),
        ],
    ])
    await message.answer(
        "<b>Экспорт диалога</b>\n\nВыберите формат:",
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("export:"))
async def on_export(callback: CallbackQuery, export_service: ExportService):
    fmt = callback.data.split(":")[1]
    await callback.answer("Экспортирую...")

    user_id = callback.from_user.id

    try:
        if fmt == "md":
            data, filename = await export_service.export_markdown(user_id)
        elif fmt == "json":
            data, filename = await export_service.export_json(user_id)
        elif fmt == "pdf":
            data, filename = await export_service.export_pdf(user_id)
        else:
            await callback.message.edit_text("Неизвестный формат.")
            return
    except Exception as e:
        logger.exception("Export failed")
        await callback.message.edit_text(f"Ошибка экспорта: {str(e)[:200]}")
        return

    if not data:
        await callback.message.edit_text("Нет сообщений для экспорта.")
        return

    doc = BufferedInputFile(data, filename=filename)
    await callback.message.answer_document(doc, caption=f"Экспорт: {filename}")
