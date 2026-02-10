"""Memory handler: view, add, remove user facts."""

import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.services.memory_service import MemoryService

logger = logging.getLogger(__name__)
router = Router()


# ═══════════════════════════════════════════════════════
#  BUTTON + COMMAND: show memories
# ═══════════════════════════════════════════════════════

@router.message(F.text == "Память")
async def memory_button(message: Message, memory_service: MemoryService):
    text = await memory_service.format_for_display(message.from_user.id)
    kb = _memory_manage_keyboard()
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.message(Command("memory"))
async def memory_command(message: Message, memory_service: MemoryService):
    args = message.text.strip().split(maxsplit=1)
    if len(args) < 2:
        text = await memory_service.format_for_display(message.from_user.id)
        kb = _memory_manage_keyboard()
        await message.answer(text, parse_mode="HTML", reply_markup=kb)
        return

    sub = args[1].strip()
    user_id = message.from_user.id

    # /memory add <category> <fact>
    if sub.lower().startswith("add "):
        rest = sub[4:].strip()
        parts = rest.split(maxsplit=1)
        if len(parts) < 2:
            await message.answer(
                "Формат: /memory add &lt;категория&gt; &lt;факт&gt;\n"
                "Пример: /memory add personal Меня зовут Ахмад",
                parse_mode="HTML",
            )
            return
        category, content = parts[0].lower(), parts[1].strip()
        # Validate category
        categories = await memory_service.get_categories(user_id)
        valid_slugs = {c["slug"] for c in categories}
        if category not in valid_slugs:
            cats_list = ", ".join(f"{c['emoji']} {c['slug']}" for c in categories)
            await message.answer(
                f"Неизвестная категория: {category}\n\n"
                f"Доступные: {cats_list}",
            )
            return
        mem_id = await memory_service.add_memory(user_id, category, content)
        if mem_id:
            emoji = memory_service.get_category_emoji(categories, category)
            await message.answer(f"Сохранено: {emoji} {content}")
        else:
            await message.answer("Ошибка при сохранении")
        return

    # /memory remove <id>
    if sub.lower().startswith("remove "):
        try:
            mem_id = int(sub[7:].strip())
        except ValueError:
            await message.answer("Формат: /memory remove &lt;id&gt;", parse_mode="HTML")
            return
        ok = await memory_service.remove_memory(mem_id, user_id)
        if ok:
            await message.answer(f"Факт #{mem_id} удалён")
        else:
            await message.answer(f"Факт #{mem_id} не найден")
        return

    # /memory clear
    if sub.lower() == "clear":
        count = await memory_service.clear_memories(user_id)
        await message.answer(f"Память очищена ({count} фактов удалено)")
        return

    # /memory category add <slug> <emoji> <label>
    if sub.lower().startswith("category add "):
        rest = sub[13:].strip()
        parts = rest.split(maxsplit=2)
        if len(parts) < 3:
            await message.answer(
                "Формат: /memory category add &lt;slug&gt; &lt;эмодзи&gt; &lt;название&gt;\n"
                "Пример: /memory category add hadith 📜 Хадисоведение",
                parse_mode="HTML",
            )
            return
        slug, emoji, label = parts[0].lower(), parts[1], parts[2]
        ok = await memory_service.add_category(user_id, slug, emoji, label)
        if ok:
            await message.answer(f"Категория создана: {emoji} {label} ({slug})")
        else:
            await message.answer(f"Категория «{slug}» уже существует")
        return

    # /memory category list
    if sub.lower().startswith("category"):
        categories = await memory_service.get_categories(user_id)
        lines = [f"{c['emoji']} <b>{c['label']}</b> ({c['slug']})" for c in categories]
        text = "<b>Категории памяти:</b>\n\n" + "\n".join(lines)
        await message.answer(text, parse_mode="HTML")
        return

    await message.answer(
        "Команды памяти:\n"
        "• /memory — показать все факты\n"
        "• /memory add &lt;категория&gt; &lt;факт&gt;\n"
        "• /memory remove &lt;id&gt;\n"
        "• /memory clear — очистить всю память\n"
        "• /memory category add &lt;slug&gt; &lt;эмодзи&gt; &lt;название&gt;\n"
        "• /memory category list",
        parse_mode="HTML",
    )


# ═══════════════════════════════════════════════════════
#  INLINE KEYBOARD
# ═══════════════════════════════════════════════════════

def _memory_manage_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Категории", callback_data="mem:cats"),
        ],
    ])


def memory_confirm_keyboard(memory_ids: list[int]) -> InlineKeyboardMarkup:
    """Keyboard for confirming auto-extracted facts."""
    ids_str = ",".join(str(i) for i in memory_ids)
    buttons = [
        [
            InlineKeyboardButton(text="Сохранить", callback_data=f"mem:confirm_all:{ids_str}"),
            InlineKeyboardButton(text="Отменить", callback_data=f"mem:reject_all:{ids_str}"),
        ],
    ]
    # Add individual reject buttons if multiple facts
    if len(memory_ids) > 1:
        buttons.append([
            InlineKeyboardButton(text="Выбрать", callback_data=f"mem:select:{ids_str}"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _select_keyboard(memory_ids: list[int], facts: list[dict]) -> InlineKeyboardMarkup:
    """Keyboard for selective confirmation of facts."""
    buttons = []
    for mid, fact in zip(memory_ids, facts):
        short = fact["fact"][:30]
        buttons.append([
            InlineKeyboardButton(text=f"\u2713 {short}", callback_data=f"mem:confirm:{mid}"),
            InlineKeyboardButton(text="\u2717", callback_data=f"mem:reject:{mid}"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ═══════════════════════════════════════════════════════
#  CALLBACKS
# ═══════════════════════════════════════════════════════

@router.callback_query(F.data == "mem:cats")
async def on_show_categories(callback: CallbackQuery, memory_service: MemoryService):
    categories = await memory_service.get_categories(callback.from_user.id)
    lines = [f"{c['emoji']} <b>{c['label']}</b> ({c['slug']})" for c in categories]
    text = "<b>Категории памяти:</b>\n\n" + "\n".join(lines)
    text += "\n\nДобавить: /memory category add &lt;slug&gt; &lt;эмодзи&gt; &lt;название&gt;"
    await callback.answer()
    await callback.message.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("mem:confirm_all:"))
async def on_confirm_all(callback: CallbackQuery, memory_service: MemoryService):
    ids_str = callback.data.split(":", 2)[2]
    ids = [int(x) for x in ids_str.split(",") if x]

    for mid in ids:
        await memory_service.confirm_memory(mid)

    await callback.answer("Все факты сохранены")
    await callback.message.edit_text(
        callback.message.text + "\n\n<i>Сохранено</i>",
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("mem:reject_all:"))
async def on_reject_all(callback: CallbackQuery, memory_service: MemoryService):
    ids_str = callback.data.split(":", 2)[2]
    ids = [int(x) for x in ids_str.split(",") if x]

    for mid in ids:
        await memory_service.reject_memory(mid)

    await callback.answer("Отменено")
    await callback.message.edit_text(
        callback.message.text + "\n\n<i>Отменено</i>",
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("mem:select:"))
async def on_select_mode(callback: CallbackQuery, memory_service: MemoryService):
    ids_str = callback.data.split(":", 2)[2]
    ids = [int(x) for x in ids_str.split(",") if x]

    # Load pending memories
    pending = await memory_service.get_pending_memories(callback.from_user.id)
    pending_map = {m.id: m for m in pending}

    facts = []
    valid_ids = []
    for mid in ids:
        if mid in pending_map:
            facts.append({"fact": pending_map[mid].content})
            valid_ids.append(mid)

    if not valid_ids:
        await callback.answer("Нет фактов для выбора")
        return

    kb = _select_keyboard(valid_ids, facts)
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=kb)


@router.callback_query(F.data.startswith("mem:confirm:"))
async def on_confirm_one(callback: CallbackQuery, memory_service: MemoryService):
    mid = int(callback.data.split(":")[2])
    await memory_service.confirm_memory(mid)
    await callback.answer(f"Факт #{mid} сохранён")


@router.callback_query(F.data.startswith("mem:reject:"))
async def on_reject_one(callback: CallbackQuery, memory_service: MemoryService):
    mid = int(callback.data.split(":")[2])
    await memory_service.reject_memory(mid)
    await callback.answer(f"Факт #{mid} удалён")
