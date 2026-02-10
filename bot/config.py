import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # Telegram
    bot_token: str = ""
    telegram_api_id: str = ""
    telegram_api_hash: str = ""
    admin_ids: list[int] = field(default_factory=list)
    use_local_api: bool = True
    local_api_url: str = "http://telegram-bot-api:8081"

    # AI Models
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_ai_api_key: str = ""
    bfl_api_key: str = ""

    # Model defaults
    default_gpt_model: str = "chatgpt-4o-latest"
    default_claude_model: str = "claude-sonnet-4-20250514"
    default_gemini_model: str = "gemini-3-pro-preview"
    default_model: str = "claude"

    # Streaming
    streaming_enabled: bool = True
    streaming_update_interval: float = 1.0

    # Context
    max_context_messages: int = 20

    # RAG / Embeddings
    embedding_model: str = "text-embedding-3-small"
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 100
    rag_top_k: int = 5

    # Search
    tavily_api_key: str = ""
    auto_search: bool = True

    # Voice (TTS/STT)
    tts_voice_ids: dict[str, str] = field(default_factory=lambda: {
        "gpt": "ash",
        "claude": "onyx",
        "gemini": "echo",
    })

    # Files
    files_dir: str = "/app/files"

    @classmethod
    def from_env(cls) -> "Config":
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        admin_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]

        return cls(
            bot_token=os.getenv("BOT_TOKEN", ""),
            telegram_api_id=os.getenv("TELEGRAM_API_ID", ""),
            telegram_api_hash=os.getenv("TELEGRAM_API_HASH", ""),
            admin_ids=admin_ids,
            use_local_api=os.getenv("USE_LOCAL_API", "true").lower() == "true",
            local_api_url=os.getenv("LOCAL_API_URL", "http://telegram-bot-api:8081"),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            google_ai_api_key=os.getenv("GOOGLE_AI_API_KEY", ""),
            bfl_api_key=os.getenv("BFL_API_KEY", ""),
            default_gpt_model=os.getenv("DEFAULT_GPT_MODEL", "chatgpt-4o-latest"),
            default_claude_model=os.getenv("DEFAULT_CLAUDE_MODEL", "claude-sonnet-4-20250514"),
            default_gemini_model=os.getenv("DEFAULT_GEMINI_MODEL", "gemini-2.0-flash"),
            default_model=os.getenv("DEFAULT_MODEL", "claude"),
            streaming_enabled=os.getenv("STREAMING_ENABLED", "true").lower() == "true",
            streaming_update_interval=float(os.getenv("STREAMING_UPDATE_INTERVAL", "1.0")),
            max_context_messages=int(os.getenv("MAX_CONTEXT_MESSAGES", "20")),
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            rag_chunk_size=int(os.getenv("RAG_CHUNK_SIZE", "800")),
            rag_chunk_overlap=int(os.getenv("RAG_CHUNK_OVERLAP", "100")),
            rag_top_k=int(os.getenv("RAG_TOP_K", "5")),
            tavily_api_key=os.getenv("TAVILY_API_KEY", ""),
            auto_search=os.getenv("AUTO_SEARCH", "true").lower() == "true",
            tts_voice_ids={
                "gpt": os.getenv("TTS_VOICE_GPT", "ash"),
                "claude": os.getenv("TTS_VOICE_CLAUDE", "onyx"),
                "gemini": os.getenv("TTS_VOICE_GEMINI", "echo"),
            },
            files_dir=os.getenv("FILES_DIR", "/app/files"),
        )


config = Config.from_env()
