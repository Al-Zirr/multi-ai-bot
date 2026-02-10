import logging

from sqlalchemy import select

from bot.config import Config
from bot.database import async_session
from bot.models.user_settings import UserSettings
from bot.services.openai_service import OpenAIService
from bot.services.anthropic_service import AnthropicService
from bot.services.gemini_service import GeminiService

logger = logging.getLogger(__name__)

PROVIDERS = {
    "gpt": {"class": OpenAIService, "display": "GPT"},
    "claude": {"class": AnthropicService, "display": "Claude"},
    "gemini": {"class": GeminiService, "display": "Gemini"},
}


class AIRouter:
    def __init__(self, cfg: Config):
        self.services: dict[str, OpenAIService | AnthropicService | GeminiService] = {}

        if cfg.openai_api_key:
            self.services["gpt"] = OpenAIService(cfg.openai_api_key, cfg.default_gpt_model)
            logger.info("OpenAI service initialized: %s", cfg.default_gpt_model)

        if cfg.anthropic_api_key:
            self.services["claude"] = AnthropicService(cfg.anthropic_api_key, cfg.default_claude_model)
            logger.info("Anthropic service initialized: %s", cfg.default_claude_model)

        if cfg.google_ai_api_key:
            self.services["gemini"] = GeminiService(cfg.google_ai_api_key, cfg.default_gemini_model)
            logger.info("Gemini service initialized: %s", cfg.default_gemini_model)

        self.default_provider = cfg.default_model

        # In-memory: user_id -> selected provider name
        self.user_models: dict[int, str] = {}
        # In-memory: user_id -> conversation history
        self.conversations: dict[int, list[dict[str, str]]] = {}
        self.max_context = cfg.max_context_messages

    def get_service(self, provider: str | None = None):
        name = provider or self.default_provider
        svc = self.services.get(name)
        if not svc:
            # fallback to any available
            for svc in self.services.values():
                return svc
            raise RuntimeError("No AI services configured")
        return svc

    def get_user_provider(self, user_id: int) -> str:
        return self.user_models.get(user_id, self.default_provider)

    def set_user_provider(self, user_id: int, provider: str):
        self.user_models[user_id] = provider

    async def load_user_provider(self, user_id: int) -> str:
        """Load from DB into cache and return provider."""
        if user_id in self.user_models:
            cached = self.user_models[user_id]
            logger.info("Model for user %d: %s (cache)", user_id, cached)
            return cached
        try:
            async with async_session() as session:
                stmt = select(UserSettings).where(UserSettings.user_id == user_id)
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()
                if row and row.selected_model and row.selected_model in self.services:
                    self.user_models[user_id] = row.selected_model
                    logger.info("Model for user %d: %s (DB)", user_id, row.selected_model)
                    return row.selected_model
                logger.info("Model for user %d: no DB record, using default %s", user_id, self.default_provider)
        except Exception:
            logger.exception("Failed to load user provider from DB")
        return self.default_provider

    async def save_user_provider(self, user_id: int, provider: str):
        """Save to cache + DB."""
        self.user_models[user_id] = provider
        try:
            async with async_session() as session:
                stmt = select(UserSettings).where(UserSettings.user_id == user_id)
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()
                if row:
                    row.selected_model = provider
                else:
                    session.add(UserSettings(user_id=user_id, selected_model=provider))
                await session.commit()
        except Exception:
            logger.exception("Failed to save user provider to DB")

    def get_display_name(self, provider: str) -> str:
        svc = self.services.get(provider)
        if svc:
            model = getattr(svc, "model", None) or getattr(svc, "model_name", "")
            return f"{svc.DISPLAY_NAME} ({model})"
        return provider

    def get_model_label(self, provider: str) -> str:
        """Clean model label for signatures, e.g. 'Claude Opus 4.6'."""
        import re
        svc = self.services.get(provider)
        if not svc:
            return provider
        model_id = getattr(svc, "model", None) or getattr(svc, "model_name", "")
        name = svc.DISPLAY_NAME
        # Remove base name prefix: "claude-opus-4-6" → "opus-4-6"
        tail = re.sub(rf"^{name.lower()}-?", "", model_id, flags=re.IGNORECASE).strip("-")
        # Remove date suffixes like -20250514
        tail = re.sub(r"-\d{8}$", "", tail)
        # Split into tokens
        tokens = tail.split("-") if tail else []
        # Build label: words capitalize, consecutive digits join with dots
        parts = []
        num_buf = []
        for t in tokens:
            if t.isdigit():
                num_buf.append(t)
            else:
                if num_buf:
                    parts.append(".".join(num_buf))
                    num_buf = []
                if t not in ("latest", "preview"):
                    parts.append(t.capitalize())
        if num_buf:
            parts.append(".".join(num_buf))
        suffix = " ".join(parts) if parts else model_id
        return f"{name} {suffix}"

    def get_history(self, user_id: int) -> list[dict[str, str]]:
        return self.conversations.get(user_id, [])

    def add_to_history(self, user_id: int, role: str, content: str):
        if user_id not in self.conversations:
            self.conversations[user_id] = []
        self.conversations[user_id].append({"role": role, "content": content})
        # Trim to max context
        if len(self.conversations[user_id]) > self.max_context:
            self.conversations[user_id] = self.conversations[user_id][-self.max_context:]

    def clear_history(self, user_id: int):
        self.conversations.pop(user_id, None)

    def available_providers(self) -> list[str]:
        return list(self.services.keys())

    def model_versions(self) -> dict[str, str]:
        """Return {provider: model_id} for all services."""
        result = {}
        for name, svc in self.services.items():
            result[name] = getattr(svc, "model", None) or getattr(svc, "model_name", name)
        return result
