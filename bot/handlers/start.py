from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from bot.config import config as app_config
from bot.keyboards.main_menu import get_main_menu
from bot.services.ai_router import AIRouter
from bot.services.balance_service import BalanceService
from bot.services.context_service import ContextService
from bot.services.quota_service import QuotaService
from bot.services.voice_service import VoiceService

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, ai_router: AIRouter):
    provider = await ai_router.load_user_provider(message.from_user.id)
    display = ai_router.get_display_name(provider)

    await message.answer(
        f"<b>Multi-AI Bot</b>\n\n"
        f"Текущая модель: {display}\n\n"
        f"Просто отправь сообщение \u2014 я отвечу.\n"
        f"/model \u2014 сменить модель\n"
        f"/clear \u2014 очистить историю\n"
        f"/context \u2014 статус контекста",
        parse_mode="HTML",
        reply_markup=get_main_menu(),
    )


@router.message(Command("clear"))
@router.message(F.text == "Очистить")
async def cmd_clear(message: Message, context_service: ContextService):
    user_id = message.from_user.id
    count = await context_service.clear_history(user_id)
    await message.answer(
        f"История очищена ({count} сообщений удалено)"
    )


@router.message(Command("context"))
@router.message(F.text == "Контекст")
async def cmd_context(message: Message, context_service: ContextService):
    user_id = message.from_user.id
    stats = await context_service.get_stats(user_id)

    text = (
        f"<b>Контекст</b>\n\n"
        f"Сообщений в БД: {stats['total_messages']}\n"
        f"Окно контекста: {stats['context_window']} / {context_service.max_context}\n"
        f"Суммаризаций: {stats['summaries']}\n"
        f"Токенов сэкономлено: ~{stats['tokens_saved']}"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "<b>Multi-AI Bot \u2014 Команды</b>\n\n"
        "/model \u2014 Выбрать модель AI\n"
        "/search \u2014 Поиск в интернете\n"
        "/balance \u2014 Балансы сервисов\n"
        "/pronounce \u2014 Словарь произношений\n"
        "/memory \u2014 Память (факты обо мне)\n"
        "/glossary \u2014 Глоссарий переводчика\n"
        "/translator_prompt \u2014 Кастомные промпты переводчика\n"
        "/imagine \u2014 Генерация изображений\n"
        "/fix \u2014 Коррекция ударений\n"
        "/context \u2014 Статус контекста\n"
        "/clear \u2014 Очистить историю диалога\n"
        "/plan \u2014 Мой план и лимиты\n"
        "/bookmarks \u2014 Мои закладки\n"
        "/export \u2014 Экспорт диалога (MD/JSON/PDF)\n"
        "/help \u2014 Эта справка\n\n"
        "<b>YouTube</b>\n"
        "Отправьте ссылку YouTube \u2014 выжимка, скачивание видео/аудио",
        parse_mode="HTML",
    )



@router.message(Command("pronounce"))
async def cmd_pronounce(message: Message, voice_service: VoiceService):
    """Manage pronunciation dictionary.

    /pronounce — list all rules
    /pronounce слово как_читать — add rule
    /pronounce -удалить слово — remove rule
    """
    args = message.text.removeprefix("/pronounce").strip()

    if not args:
        # List all rules
        rules = await voice_service.list_pronunciations()
        if not rules:
            await message.answer(
                "<b>Словарь произношений</b> пуст.\n\n"
                "Добавить: <code>/pronounce слово как_читать</code>\n"
                "Удалить: <code>/pronounce -удалить слово</code>",
                parse_mode="HTML",
            )
            return
        lines = [f"<b>Словарь произношений</b> ({len(rules)}):\n"]
        for word, repl in rules:
            lines.append(f"<code>{word}</code> \u2192 <code>{repl}</code>")
        text = "\n".join(lines)
        # Split if too long
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for p in parts:
                await message.answer(p, parse_mode="HTML")
        else:
            await message.answer(text, parse_mode="HTML")
        return

    # Remove rule
    if args.startswith("-удалить ") or args.startswith("-del "):
        word = args.split(" ", 1)[1].strip()
        ok = await voice_service.remove_pronunciation(word)
        if ok:
            await message.answer(f"Удалено: <code>{word}</code>", parse_mode="HTML")
        else:
            await message.answer(f"Слово <code>{word}</code> не найдено", parse_mode="HTML")
        return

    # Add rule: /pronounce слово как_читать
    parts = args.split(None, 1)
    if len(parts) < 2:
        await message.answer(
            "<b>Использование:</b>\n"
            "<code>/pronounce аль-Газали аль Газаали</code>\n"
            "<code>/pronounce -удалить аль-Газали</code>",
            parse_mode="HTML",
        )
        return

    word, replacement = parts[0], parts[1]
    ok = await voice_service.add_pronunciation(word, replacement)
    if ok:
        await message.answer(
            f"Добавлено: <code>{word}</code> \u2192 <code>{replacement}</code>",
            parse_mode="HTML",
        )
    else:
        await message.answer("Ошибка сохранения")


@router.message(Command("fix"))
async def cmd_fix(message: Message, voice_service: VoiceService):
    """Manage stress overrides (post-russtress corrections).

    /fix — list all overrides
    /fix слово замена — add override (e.g. /fix до́ма до́ма)
    /fix -удалить слово — remove override
    """
    from sqlalchemy import select, delete as sql_delete
    from bot.database import async_session
    from bot.models.stress_override import StressOverride

    args = message.text.removeprefix("/fix").strip()

    if not args:
        # List all overrides
        async with async_session() as session:
            result = await session.execute(
                select(StressOverride).order_by(StressOverride.word)
            )
            rows = result.scalars().all()
        if not rows:
            await message.answer(
                "<b>Коррекции ударений</b> пусты.\n\n"
                "Добавить: <code>/fix слово замена</code>\n"
                "Удалить: <code>/fix -удалить слово</code>",
                parse_mode="HTML",
            )
            return
        lines = [f"<b>Коррекции ударений</b> ({len(rows)}):\n"]
        for row in rows:
            lines.append(f"<code>{row.word}</code> \u2192 <code>{row.replacement}</code>")
        text = "\n".join(lines)
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for p in parts:
                await message.answer(p, parse_mode="HTML")
        else:
            await message.answer(text, parse_mode="HTML")
        return

    # Remove override
    if args.startswith("-удалить ") or args.startswith("-del "):
        word = args.split(" ", 1)[1].strip()
        async with async_session() as session:
            result = await session.execute(
                sql_delete(StressOverride).where(StressOverride.word == word)
            )
            await session.commit()
        if result.rowcount > 0:
            voice_service.pipeline.invalidate_overrides_cache()
            await message.answer(f"Удалено: <code>{word}</code>", parse_mode="HTML")
        else:
            await message.answer(f"Слово <code>{word}</code> не найдено", parse_mode="HTML")
        return

    # Add override: /fix слово замена
    parts = args.split(None, 1)
    if len(parts) < 2:
        await message.answer(
            "<b>Использование:</b>\n"
            "<code>/fix слово правильное_произношение</code>\n"
            "<code>/fix -удалить слово</code>",
            parse_mode="HTML",
        )
        return

    word, replacement = parts[0], parts[1]
    async with async_session() as session:
        existing_q = await session.execute(
            select(StressOverride).where(StressOverride.word == word)
        )
        existing = existing_q.scalar_one_or_none()
        if existing:
            existing.replacement = replacement
        else:
            session.add(StressOverride(word=word, replacement=replacement))
        await session.commit()
    voice_service.pipeline.invalidate_overrides_cache()
    await message.answer(
        f"Коррекция: <code>{word}</code> \u2192 <code>{replacement}</code>",
        parse_mode="HTML",
    )


@router.message(Command("balance"))
@router.message(F.text == "Баланс")
async def cmd_balance(message: Message, balance_service: BalanceService):
    balances = await balance_service.get_all_balances()
    if not balances:
        await message.answer("Нет данных о балансах")
        return

    lines = ["<b>Балансы сервисов</b>\n"]
    for b in balances:
        svc = b["service"].capitalize()
        if b["unit"] == "$":
            bal = f"${b['balance']:.2f}"
            spent = f"${b['spent']:.2f}"
        else:
            bal = f"{int(b['balance'])} {b['unit']}"
            spent = f"{int(b['spent'])} {b['unit']}"
        warn = " !" if b["warn"] else ""
        lines.append(f"<b>{svc}</b>: {bal}{warn}  (израсходовано: {spent})")

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("setbalance"))
async def cmd_setbalance(message: Message, balance_service: BalanceService):
    """Usage: /setbalance openai 15.00"""
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer(
            "<b>Использование:</b>\n"
            "<code>/setbalance openai 15.00</code>\n"
            "<code>/setbalance tavily 1000</code>",
            parse_mode="HTML",
        )
        return
    service_name = parts[1].lower()
    try:
        new_val = float(parts[2])
    except ValueError:
        await message.answer("Неверное значение")
        return
    await balance_service.set_balance(service_name, new_val)
    await message.answer(f"Баланс <b>{service_name}</b> установлен: {new_val}", parse_mode="HTML")


@router.message(Command("plan"))
async def cmd_plan(message: Message, quota_service: QuotaService):
    """Show current plan and usage."""
    user_id = message.from_user.id
    info = await quota_service.get_usage_info(user_id)

    plan_labels = {"free": "Free", "basic": "Basic", "pro": "Pro"}
    plan_label = plan_labels.get(info["plan"], info["plan"])

    # Tokens
    if info["tokens_limit"] == 0:
        tokens_str = f"{info['tokens_used']:,} / безлимит"
    else:
        tokens_str = f"{info['tokens_used']:,} / {info['tokens_limit']:,}"

    # Images
    if info["images_limit"] == 0:
        images_str = f"{info['images_used']} / безлимит"
    else:
        images_str = f"{info['images_used']} / {info['images_limit']}"

    # YouTube
    yt_str = "доступно" if info["youtube_allowed"] else "недоступно"

    text = (
        f"<b>Ваш план: {plan_label}</b>\n\n"
        f"Токены сегодня: {tokens_str}\n"
        f"Изображения сегодня: {images_str}\n"
        f"YouTube скачивание: {yt_str}\n\n"
        f"Счётчики обнуляются ежедневно."
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("setplan"))
async def cmd_setplan(message: Message, quota_service: QuotaService):
    """Admin: set user plan. Usage: /setplan <telegram_id> <plan>"""
    user_id = message.from_user.id
    if user_id not in app_config.admin_ids:
        await message.answer("Команда доступна только администраторам.")
        return

    parts = message.text.split()
    if len(parts) != 3:
        await message.answer(
            "<b>Использование:</b>\n"
            "<code>/setplan telegram_id plan</code>\n\n"
            "Планы: <code>free</code>, <code>basic</code>, <code>pro</code>",
            parse_mode="HTML",
        )
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный telegram_id")
        return

    plan = parts[2].lower()
    ok = await quota_service.set_plan(target_id, plan)
    if ok:
        await message.answer(
            f"План пользователя <code>{target_id}</code> установлен: <b>{plan}</b>",
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"Ошибка. Проверьте telegram_id и план (free/basic/pro).",
        )
