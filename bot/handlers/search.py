import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import Config
from bot.keyboards.model_select import get_response_keyboard
from bot.services.ai_router import AIRouter
from bot.services.balance_service import BalanceService
from bot.services.context_service import ContextService
from bot.services.search_service import SearchService
from bot.services.streaming_service import StreamingService
from bot.services.telegraph_service import TelegraphService
from bot.utils.prompts import SEARCH_SYSTEM_PROMPT

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("search"))
async def cmd_search(
    message: Message,
    ai_router: AIRouter,
    config: Config,
    context_service: ContextService,
    search_service: SearchService,
    telegraph_service: TelegraphService,
    balance_service: BalanceService,
):
    query = message.text.removeprefix("/search").strip()
    if not query:
        await message.answer(
            "Использование: "
            "<code>/search ваш запрос</code>",
            parse_mode="HTML",
        )
        return

    await _do_search(message, query, ai_router, config, context_service, search_service, telegraph_service, balance_service)


@router.message(F.text == "Поиск")
async def btn_search(message: Message):
    await message.answer(
        "Отправь запрос командой:\n"
        "<code>/search ваш запрос</code>",
        parse_mode="HTML",
    )


async def _do_search(
    message: Message,
    query: str,
    ai_router: AIRouter,
    config: Config,
    context_service: ContextService,
    search_service: SearchService,
    telegraph_service: TelegraphService | None = None,
    balance_service: BalanceService | None = None,
):
    user_id = message.from_user.id

    waiting = await message.answer(
        f"Ищу: <i>{query[:100]}</i>...",
        parse_mode="HTML",
    )

    search_results = await search_service.search_for_ai(query)

    # Track Tavily usage
    if balance_service:
        await balance_service.track_tavily()

    if not search_results:
        await waiting.edit_text("Ничего не найдено.")
        return

    await waiting.edit_text(
        f"Найдено. Генерирую ответ..."
    )

    # Build augmented prompt
    augmented = (
        f"АКТУАЛЬНЫЕ ДАННЫЕ ИЗ ИНТЕРНЕТА (используй их как факт, "
        f"не пиши что не имеешь доступа к данным):\n"
        f"{search_results}\n\n"
        f"Вопрос пользователя: {query}\n\n"
        f"ВАЖНО: Ответь конкретно, используя данные выше. "
        f"Не предлагай пользователю искать самому."
    )

    await context_service.add_message(user_id, "user", f"[Поиск] {query}")
    history = [{"role": "user", "content": augmented}]

    provider = await ai_router.load_user_provider(user_id)
    service = ai_router.get_service(provider)
    display = ai_router.get_display_name(provider)

    await waiting.delete()

    label = ai_router.get_model_label(provider)

    balance_str = ""
    if balance_service:
        balance_str = await balance_service.format_balance_for_signature(provider)

    generator = service.generate_stream(history, system_prompt=SEARCH_SYSTEM_PROMPT)
    _, full_text = await StreamingService.stream_response(
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
        if balance_service and service.last_usage:
            await balance_service.track_ai_usage(
                provider, service.last_usage["input_tokens"], service.last_usage["output_tokens"]
            )
