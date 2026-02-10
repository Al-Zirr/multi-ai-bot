import logging

from aiogram import Router, F, Bot
from aiogram.types import Message

from bot.config import Config
from bot.services.ai_router import AIRouter
from bot.services.context_service import ContextService
from bot.services.file_service import FileService
from bot.services.rag_service import RAGService
from bot.services.balance_service import BalanceService
from bot.services.streaming_service import StreamingService
from bot.services.telegraph_service import TelegraphService
from bot.keyboards.model_select import get_response_keyboard
from bot.utils.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.document)
async def handle_document(
    message: Message,
    bot: Bot,
    ai_router: AIRouter,
    config: Config,
    context_service: ContextService,
    file_service: FileService,
    rag_service: RAGService,
    telegraph_service: TelegraphService,
    balance_service: BalanceService,
):
    doc = message.document
    filename = doc.file_name or "unknown"
    caption = message.caption or ""

    # Check file type
    from bot.services.file_service import SUPPORTED_TYPES
    from pathlib import Path

    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_TYPES:
        supported = ", ".join(sorted(SUPPORTED_TYPES.keys()))
        await message.answer(
            f"Формат <b>{ext}</b> не поддерживается.\n"
            f"Поддерживаются: {supported}",
            parse_mode="HTML",
        )
        return

    waiting = await message.answer(
        f"Получаю <b>{filename}</b>...",
        parse_mode="HTML",
    )

    # Download file
    file = await bot.get_file(doc.file_id)
    file_bytes = await bot.download_file(file.file_path)
    data = file_bytes.read()

    # Save and extract text
    user_id = message.from_user.id
    pf = await file_service.save_file(user_id, filename, data)

    if not pf:
        await waiting.edit_text("Не удалось обработать файл")
        return

    emoji = file_service.get_file_type_emoji(pf.file_type)
    text_len = len(pf.extracted_text) if pf.extracted_text else 0

    # Index with RAG if text was extracted
    chunk_count = 0
    if pf.extracted_text:
        try:
            chunk_count = await rag_service.index_file(pf.id, pf.extracted_text)
        except Exception:
            logger.exception("RAG indexing failed for file %d", pf.id)

    status = (
        f"<b>{pf.filename}</b>\n"
        f"Тип: {pf.file_type} | {pf.file_size // 1024} KB\n"
        f"Извлечено: {text_len} символов\n"
    )
    if chunk_count:
        status += f"RAG: {chunk_count} чанков проиндексировано\n"

    # If user added a caption (question about the file), answer it
    if caption:
        status += "\nФайл загружен. Отвечаю на вопрос..."
        await waiting.edit_text(status, parse_mode="HTML")

        # Build context: RAG search + question
        rag_context = await rag_service.build_context(caption, [pf.id])
        if rag_context:
            augmented_prompt = (
                f"\u041a\u043e\u043d\u0442\u0435\u043a\u0441\u0442 \u0438\u0437 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0430:\n{rag_context}\n\n"
                f"\u0412\u043e\u043f\u0440\u043e\u0441: {caption}"
            )
        else:
            # Fallback: use extracted text directly (truncated)
            doc_text = pf.extracted_text[:8000] if pf.extracted_text else ""
            augmented_prompt = (
                f"\u041a\u043e\u043d\u0442\u0435\u043a\u0441\u0442 \u0438\u0437 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0430:\n{doc_text}\n\n"
                f"\u0412\u043e\u043f\u0440\u043e\u0441: {caption}"
            )

        provider = await ai_router.load_user_provider(user_id)
        service = ai_router.get_service(provider)
        display = ai_router.get_display_name(provider)

        await context_service.add_message(user_id, "user", augmented_prompt)
        history = await context_service.get_context_for_ai(user_id)

        label = ai_router.get_model_label(provider)

        balance_str = ""
        if balance_service:
            balance_str = await balance_service.format_balance_for_signature(provider)

        generator = service.generate_stream(history, system_prompt=SYSTEM_PROMPT)
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
    else:
        status += "\nФайл загружен. Отправь вопрос по нему."
        await waiting.edit_text(status, parse_mode="HTML")
