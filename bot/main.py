import asyncio
import logging
import logging.handlers
import os

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.types import BotCommand, ErrorEvent

from bot.config import config
from bot.database import init_db
from bot.handlers import start, chat, model_switch, debate, files, images, imagegen, search, voice, translator, memory, settings, youtube, bookmarks
from bot.middlewares.auth import AuthMiddleware
from bot.services.ai_router import AIRouter
from bot.services.balance_service import BalanceService
from bot.services.context_service import ContextService
from bot.services.file_service import FileService
from bot.services.rag_service import RAGService
from bot.services.search_service import SearchService
from bot.services.memory_service import MemoryService
from bot.services.telegraph_service import TelegraphService
from bot.services.translator_service import TranslatorService
from bot.services.image_service import ImageService
from bot.services.settings_service import SettingsService
from bot.services.voice_service import VoiceService
from bot.services.youtube_service import YouTubeService
from bot.services.bookmark_service import BookmarkService
from bot.services.export_service import ExportService
from bot.services.quota_service import QuotaService

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DIR = os.getenv("LOG_DIR", "/app/logs")
LOG_FILE = os.path.join(LOG_DIR, "bot.log")

os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8",
)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
logging.getLogger().addHandler(file_handler)

logger = logging.getLogger(__name__)


async def main():
    proxy_url = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY") or None

    # Bot setup
    if config.use_local_api:
        local_server = TelegramAPIServer.from_base(
            config.local_api_url, is_local=True
        )
        session = AiohttpSession(api=local_server)
        bot = Bot(token=config.bot_token, session=session)
        logger.info("Using Telegram Bot API Local Server: %s", config.local_api_url)
    else:
        session = AiohttpSession(proxy=proxy_url) if proxy_url else AiohttpSession()
        bot = Bot(token=config.bot_token, session=session)
        logger.info("Using Telegram Cloud API (proxy: %s)", proxy_url or "none")

    # Init database
    await init_db()
    logger.info("Database initialized")

    # Init AI services
    ai_router = AIRouter(config)
    context_service = ContextService(max_context=config.max_context_messages)
    file_service = FileService(config.files_dir)
    rag_service = RAGService(
        openai_api_key=config.openai_api_key,
        embedding_model=config.embedding_model,
        chunk_size=config.rag_chunk_size,
        chunk_overlap=config.rag_chunk_overlap,
        top_k=config.rag_top_k,
    )

    search_service = SearchService(
        api_key=config.tavily_api_key,
        auto_search=config.auto_search,
    ) if config.tavily_api_key else None

    dp = Dispatcher()
    dp["ai_router"] = ai_router
    dp["config"] = config
    dp["context_service"] = context_service
    dp["file_service"] = file_service
    dp["rag_service"] = rag_service
    dp["search_service"] = search_service
    dp["telegraph_service"] = TelegraphService()
    dp["balance_service"] = BalanceService()
    dp["settings_service"] = SettingsService()

    from openai import AsyncOpenAI
    openai_client = AsyncOpenAI(api_key=config.openai_api_key)
    dp["memory_service"] = MemoryService(openai_client=openai_client)

    dp["translator_service"] = TranslatorService(
        ai_router=ai_router,
        openai_api_key=config.openai_api_key,
        embedding_model=config.embedding_model,
    )

    dp["image_service"] = ImageService(
        openai_api_key=config.openai_api_key,
        google_api_key=config.google_ai_api_key,
        bfl_api_key=config.bfl_api_key,
    )

    voice_service = VoiceService(
        openai_api_key=config.openai_api_key,
        voice_ids=config.tts_voice_ids,
    ) if config.openai_api_key else None
    dp["voice_service"] = voice_service

    dp["youtube_service"] = YouTubeService(
        proxy=proxy_url,
        files_dir=config.files_dir,
        use_local_api=config.use_local_api,
    )

    dp["bookmark_service"] = BookmarkService()
    dp["export_service"] = ExportService()

    quota_service = QuotaService()
    dp["quota_service"] = quota_service

    # Middlewares
    dp.message.middleware(AuthMiddleware(config.admin_ids, quota_service=quota_service))
    dp.callback_query.middleware(AuthMiddleware(config.admin_ids, quota_service=quota_service))

    # Routers (order matters: specific first, catch-all last)
    dp.include_router(start.router)
    dp.include_router(settings.router)
    dp.include_router(model_switch.router)
    dp.include_router(debate.router)
    dp.include_router(search.router)
    dp.include_router(translator.router)
    dp.include_router(files.router)
    dp.include_router(images.router)
    dp.include_router(voice.router)
    dp.include_router(memory.router)
    dp.include_router(imagegen.router)
    dp.include_router(youtube.router)
    dp.include_router(bookmarks.router)
    dp.include_router(chat.router)

    # Global error handler
    @dp.errors()
    async def on_error(event: ErrorEvent):
        logger.exception("Unhandled error: %s", event.exception)
        # Try to notify the user
        try:
            update = event.update
            msg = None
            if update.message:
                msg = update.message
            elif update.callback_query:
                msg = update.callback_query.message
            if msg:
                await msg.answer("Произошла ошибка, попробуйте ещё раз.")
        except Exception:
            pass
        return True  # suppress further propagation

    # Cleanup webhook/old state
    await bot.delete_webhook(drop_pending_updates=True)

    # Register bot commands for menu button
    await bot.set_my_commands([
        BotCommand(command="model", description="Выбрать модель AI"),
        BotCommand(command="search", description="Поиск в интернете"),
        BotCommand(command="balance", description="Балансы сервисов"),
        BotCommand(command="pronounce", description="Словарь произношений"),
        BotCommand(command="memory", description="Память (факты обо мне)"),
        BotCommand(command="glossary", description="Глоссарий переводчика"),
        BotCommand(command="translator_prompt", description="Промпты переводчика"),
        BotCommand(command="imagine", description="Генерация изображений"),
        BotCommand(command="fix", description="Коррекция ударений"),
        BotCommand(command="bookmarks", description="Мои закладки"),
        BotCommand(command="export", description="Экспорт диалога"),
        BotCommand(command="context", description="Статус контекста"),
        BotCommand(command="clear", description="Очистить историю"),
        BotCommand(command="plan", description="Мой план и лимиты"),
        BotCommand(command="help", description="Справка"),
    ])

    logger.info("Bot starting... Admin IDs: %s", config.admin_ids)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
