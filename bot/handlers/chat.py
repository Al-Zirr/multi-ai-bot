import asyncio
import logging
import time

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from bot.config import Config
from bot.handlers.debate import save_debate_state, _debate_keyboard
from bot.keyboards.model_select import get_response_keyboard
from bot.services.ai_router import AIRouter
from bot.services.context_service import ContextService
from bot.services.file_service import FileService
from bot.services.rag_service import RAGService
from bot.services.search_service import SearchService
from bot.services.streaming_service import StreamingService, _split_text, _send_html_new
from bot.services.balance_service import BalanceService
from bot.services.memory_service import MemoryService
from bot.services.settings_service import SettingsService
from bot.services.telegraph_service import TelegraphService
from bot.services.voice_service import VoiceService
from bot.services.quota_service import QuotaService
from bot.utils.formatting import md_to_html
from bot.utils.prompts import SYSTEM_PROMPT, STYLE_PREFIXES

logger = logging.getLogger(__name__)
router = Router()

# Store last user message per user for regeneration
_last_user_message: dict[int, str] = {}


@router.message(F.text)
async def handle_text(
    message: Message,
    ai_router: AIRouter,
    config: Config,
    context_service: ContextService,
    file_service: FileService,
    rag_service: RAGService,
    search_service: SearchService,
    telegraph_service: TelegraphService,
    voice_service: VoiceService,
    balance_service: BalanceService,
    memory_service: MemoryService,
    settings_service: SettingsService,
    quota_service: QuotaService,
):
    user_id = message.from_user.id
    text = message.text.strip()

    # Check token quota
    allowed, error_msg = await quota_service.check_tokens(user_id)
    if not allowed:
        await message.answer(error_msg, parse_mode="HTML")
        return

    _last_user_message[user_id] = text
    provider = await ai_router.load_user_provider(user_id)

    if provider == "all":
        await _ask_all(message, text, ai_router, config, search_service, telegraph_service, balance_service, settings_service, quota_service)
        await ai_router.save_user_provider(user_id, ai_router.default_provider)
        return

    await _ask_single(message, text, provider, ai_router, config, context_service, rag_service, file_service, search_service, telegraph_service, voice_service, balance_service, memory_service, settings_service, quota_service)


async def _ask_single(
    message: Message,
    text: str,
    provider: str,
    ai_router: AIRouter,
    config: Config,
    context_service: ContextService,
    rag_service: RAGService | None = None,
    file_service: FileService | None = None,
    search_service: SearchService | None = None,
    telegraph_service: TelegraphService | None = None,
    voice_service: VoiceService | None = None,
    balance_service: BalanceService | None = None,
    memory_service: MemoryService | None = None,
    settings_service: SettingsService | None = None,
    quota_service: QuotaService | None = None,
):
    user_id = message.from_user.id
    service = ai_router.get_service(provider)

    # Load user settings
    user_settings = await settings_service.get(user_id) if settings_service else None

    # Check for TTS trigger
    from bot.handlers.voice import _strip_tts_trigger, _send_tts
    clean_text, tts_mode = _strip_tts_trigger(text)

    # "direct" mode: just TTS the user's text, no AI
    if tts_mode == "direct" and clean_text and voice_service:
        user_voice = user_settings.tts_voice if user_settings else ""
        await _send_tts(message, clean_text, voice_service, balance_service, provider, user_voice=user_voice)
        return

    if tts_mode and clean_text:
        text = clean_text

    # Check if user has files and augment with RAG context
    user_text = text
    if rag_service and file_service:
        user_files = await file_service.get_user_files(user_id)
        if user_files:
            file_ids = [f.id for f in user_files]
            rag_context = await rag_service.build_context(text, file_ids)
            if rag_context:
                user_text = (
                    f"\u041a\u043e\u043d\u0442\u0435\u043a\u0441\u0442 \u0438\u0437 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u043e\u0432:\n{rag_context}\n\n"
                    f"\u0412\u043e\u043f\u0440\u043e\u0441: {text}"
                )

    # Auto-search: if text contains search triggers, search the web
    auto_search_on = user_settings.auto_search if user_settings else True
    if search_service and auto_search_on:
        should = search_service.should_search(text)
        logger.info("Auto-search check: '%s' → %s", text[:50], should)
        if should:
            search_results = await search_service.search_for_ai(text)
            logger.info("Tavily returned %d chars", len(search_results) if search_results else 0)
            if balance_service:
                await balance_service.track_tavily()
            if search_results:
                user_text = (
                    f"АКТУАЛЬНЫЕ ДАННЫЕ ИЗ ИНТЕРНЕТА (используй их как факт, "
                    f"не пиши что не имеешь доступа к данным):\n"
                    f"{search_results}\n\n"
                    f"Вопрос пользователя: {text}\n\n"
                    f"ВАЖНО: Ответь конкретно, используя данные выше. "
                    f"Не предлагай пользователю искать самому."
                )
    else:
        logger.warning("search_service is None — Tavily not configured")

    # Save user message to DB (original text, not augmented)
    await context_service.add_message(user_id, "user", text)

    # Build context from DB (summaries + recent messages)
    history = await context_service.get_context_for_ai(user_id, ai_service=service)

    # Replace last message with augmented version if needed
    if user_text != text and history:
        history[-1] = {"role": "user", "content": user_text}

    display = ai_router.get_display_name(provider)
    label = ai_router.get_model_label(provider)

    # Log what is being sent
    last_content = history[-1]["content"] if history else ""
    logger.info(
        "Sending to %s: %d messages, last msg %d chars, has_search=%s",
        provider, len(history), len(last_content),
        "АКТУАЛЬНЫЕ ДАННЫЕ" in last_content,
    )

    # Get balance for signature
    balance_str = ""
    if balance_service:
        balance_str = await balance_service.format_balance_for_signature(provider)

    # Build system prompt with style prefix and user memories
    style = user_settings.response_style if user_settings else "medium"
    system_prompt = STYLE_PREFIXES.get(style, "") + SYSTEM_PROMPT
    if memory_service:
        memory_block = await memory_service.format_for_prompt(user_id)
        if memory_block:
            system_prompt = SYSTEM_PROMPT + "\n\n" + memory_block

    # Stream response
    generator = service.generate_stream(history, system_prompt=system_prompt)
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

        # Track token usage
        if balance_service and service.last_usage:
            await balance_service.track_ai_usage(
                provider,
                service.last_usage["input_tokens"],
                service.last_usage["output_tokens"],
            )

        # Track quota
        if quota_service and service.last_usage:
            total_tokens = service.last_usage["input_tokens"] + service.last_usage["output_tokens"]
            await quota_service.track_token_usage(user_id, total_tokens)

        if tts_mode == "ai" and voice_service:
            user_voice = user_settings.tts_voice if user_settings else ""
            await _send_tts(message, full_text, voice_service, balance_service, provider, user_voice=user_voice)

        # Auto-extract facts from user message (fire-and-forget)
        auto_memory_on = user_settings.auto_memory if user_settings else True
        if memory_service and auto_memory_on and memory_service.should_extract(text, user_id):
            try:
                facts = await memory_service.extract_facts(text, user_id)
                if facts:
                    mem_ids = await memory_service.save_extracted_facts(user_id, facts)
                    if mem_ids:
                        categories = await memory_service.get_categories(user_id)
                        lines = []
                        for fact in facts:
                            emoji = memory_service.get_category_emoji(categories, fact["category"])
                            lines.append(f"• {emoji} {fact['fact']}")
                        confirm_text = "Я запомнил:\n" + "\n".join(lines)
                        from bot.handlers.memory import memory_confirm_keyboard
                        kb = memory_confirm_keyboard(mem_ids)
                        await message.answer(confirm_text, reply_markup=kb)
            except Exception:
                logger.exception("Memory auto-extraction failed")


async def _ask_all(
    message: Message,
    text: str,
    ai_router: AIRouter,
    config: Config,
    search_service: SearchService | None = None,
    telegraph_service: TelegraphService | None = None,
    balance_service: BalanceService | None = None,
    settings_service: SettingsService | None = None,
    quota_service: QuotaService | None = None,
):
    """Send question to all available models in parallel."""
    user_id = message.from_user.id
    providers = ai_router.available_providers()

    if not providers:
        await message.answer("Нет доступных моделей")
        return

    waiting_msg = await message.answer(
        "Спрашиваю все модели..."
    )

    # Auto-search for "ask all" mode too
    user_settings = await settings_service.get(user_id) if settings_service else None
    auto_search_on = user_settings.auto_search if user_settings else True
    user_text = text
    if search_service and auto_search_on and search_service.should_search(text):
        search_results = await search_service.search_for_ai(text)
        if search_results:
            user_text = (
                f"АКТУАЛЬНЫЕ ДАННЫЕ ИЗ ИНТЕРНЕТА (используй их как факт, "
                f"не пиши что не имеешь доступа к данным):\n"
                f"{search_results}\n\n"
                f"Вопрос пользователя: {text}\n\n"
                f"ВАЖНО: Ответь конкретно, используя данные выше. "
                f"Не предлагай пользователю искать самому."
            )
            logger.info("Auto-search in ask_all: %d chars from Tavily", len(search_results))

    msg_list = [{"role": "user", "content": user_text}]

    async def _get_response(prov: str) -> tuple[str, str, str, float]:
        svc = ai_router.get_service(prov)
        display = ai_router.get_display_name(prov)
        start = time.monotonic()
        try:
            result = await svc.generate(msg_list, system_prompt=SYSTEM_PROMPT)
            elapsed = time.monotonic() - start
            # Track usage
            if balance_service and svc.last_usage:
                await balance_service.track_ai_usage(
                    prov, svc.last_usage["input_tokens"], svc.last_usage["output_tokens"]
                )
            # Track quota
            if quota_service and svc.last_usage:
                total_tokens = svc.last_usage["input_tokens"] + svc.last_usage["output_tokens"]
                await quota_service.track_token_usage(user_id, total_tokens)
            return prov, display, result, elapsed
        except Exception as e:
            elapsed = time.monotonic() - start
            return prov, display, f"Ошибка: {e}", elapsed

    results = await asyncio.gather(*[_get_response(p) for p in providers])

    # Build answers dict for debate state
    answers_for_debate: dict[str, tuple[str, float]] = {}
    from bot.services.streaming_service import _make_signature
    html_parts = []
    timings = []
    for prov, display, text_result, elapsed in results:
        answers_for_debate[prov] = (text_result, elapsed)
        label = ai_router.get_model_label(prov)
        # Convert each model's answer to HTML separately, then append raw HTML signature
        part_html = md_to_html(f"{display}:\n{text_result}") + _make_signature(label)
        html_parts.append(part_html)
        name_short = display.split(" ", 1)[-1] if " " in display else display
        timings.append(f"{name_short} {elapsed:.1f}с")

    combined_html = "\n\n\u2501\u2501\u2501\n\n".join(html_parts)
    combined_html += f"\n\n{' | '.join(timings)}"

    # Save state for debates
    save_debate_state(user_id, text, answers_for_debate)

    # Delete waiting message and send result with debate button
    await waiting_msg.delete()

    debate_kb = _debate_keyboard(has_debate=False)

    if len(combined_html) <= 4096:
        try:
            await message.answer(combined_html, parse_mode="HTML", reply_markup=debate_kb)
        except Exception:
            # Fallback plain
            plain_parts = []
            for prov, display, text_result, elapsed in results:
                label = ai_router.get_model_label(prov)
                plain_parts.append(f"{display}:\n{text_result}\n\n\u2014 {label}")
            combined_plain = "\n\n\u2501\u2501\u2501\n\n".join(plain_parts)
            await message.answer(combined_plain, reply_markup=debate_kb)
    else:
        # Send each model's answer as a separate message
        for i, part_html in enumerate(html_parts):
            is_last = i == len(html_parts) - 1
            markup = debate_kb if is_last else None
            try:
                await message.answer(part_html, parse_mode="HTML", reply_markup=markup)
            except Exception:
                prov, display, text_result, elapsed = results[i]
                label = ai_router.get_model_label(prov)
                await message.answer(f"{display}:\n{text_result}\n\n\u2014 {label}", reply_markup=markup)


# --- Callback handlers for response buttons ---


@router.callback_query(F.data == "regen")
async def on_regenerate(
    callback: CallbackQuery,
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
    user_id = callback.from_user.id
    text = _last_user_message.get(user_id)

    if not text:
        await callback.answer(
            "Нет сообщения для перегенерации",
            show_alert=True,
        )
        return

    # Check token quota
    allowed, error_msg = await quota_service.check_tokens(user_id)
    if not allowed:
        await callback.answer("Лимит токенов исчерпан", show_alert=True)
        return

    await callback.answer("Перегенерирую...")
    provider = await ai_router.load_user_provider(user_id)

    await _ask_single(callback.message, text, provider, ai_router, config, context_service, rag_service, file_service, search_service, telegraph_service, voice_service, balance_service, settings_service=settings_service, quota_service=quota_service)


@router.callback_query(F.data.startswith("ask:"))
async def on_ask_other_model(
    callback: CallbackQuery, ai_router: AIRouter, config: Config, telegraph_service: TelegraphService, voice_service: VoiceService, balance_service: BalanceService, quota_service: QuotaService,
):
    user_id = callback.from_user.id
    provider = callback.data.split(":")[1]
    text = _last_user_message.get(user_id)

    if not text:
        await callback.answer(
            "Нет сообщения",
            show_alert=True,
        )
        return

    # Check token quota
    allowed, error_msg = await quota_service.check_tokens(user_id)
    if not allowed:
        await callback.answer("Лимит токенов исчерпан", show_alert=True)
        return

    # Switch active model to the one user clicked
    await ai_router.save_user_provider(user_id, provider)

    display = ai_router.get_display_name(provider)
    label = ai_router.get_model_label(provider)
    await callback.answer(f"{label} — теперь активная модель")

    # Ask with just the last user message (no history context for cross-model)
    messages = [{"role": "user", "content": text}]
    service = ai_router.get_service(provider)

    balance_str = ""
    if balance_service:
        balance_str = await balance_service.format_balance_for_signature(provider)

    generator = service.generate_stream(messages, system_prompt=SYSTEM_PROMPT)
    _, full_text = await StreamingService.stream_response(
        message=callback.message,
        generator=generator,
        model_display=display,
        update_interval=config.streaming_update_interval,
        reply_markup=get_response_keyboard(provider, ai_router.model_versions()),
        model_label=label,
        telegraph_service=telegraph_service,
        balance_str=balance_str,
    )

    if full_text and balance_service and service.last_usage:
        await balance_service.track_ai_usage(
            provider, service.last_usage["input_tokens"], service.last_usage["output_tokens"]
        )

    # Track quota
    if full_text and quota_service and service.last_usage:
        total_tokens = service.last_usage["input_tokens"] + service.last_usage["output_tokens"]
        await quota_service.track_token_usage(user_id, total_tokens)
