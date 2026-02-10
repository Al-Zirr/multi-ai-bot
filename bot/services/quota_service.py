"""Quota service: per-user plans, token/image limits, daily reset."""

import logging
from datetime import date

from sqlalchemy import select, update

from bot.database import async_session
from bot.models.user import User

logger = logging.getLogger(__name__)

PLAN_LIMITS = {
    "free": {
        "tokens_limit": 10_000,
        "images_limit": 3,
        "youtube_allowed": False,
    },
    "basic": {
        "tokens_limit": 100_000,
        "images_limit": 20,
        "youtube_allowed": True,
    },
    "pro": {
        "tokens_limit": 0,  # 0 = unlimited
        "images_limit": 0,
        "youtube_allowed": True,
    },
}


class QuotaService:

    def __init__(self):
        self._cache: dict[int, User] = {}

    async def get_or_create_user(self, telegram_id: int, username: str | None = None) -> User:
        """Auto-register user on first message. Returns User from cache or DB."""
        if telegram_id in self._cache:
            return self._cache[telegram_id]

        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()

            if user is None:
                user = User(telegram_id=telegram_id, username=username)
                session.add(user)
                await session.commit()
                await session.refresh(user)
                logger.info("New user registered: %s (@%s)", telegram_id, username)
            elif username and user.username != username:
                user.username = username
                await session.commit()

            self._cache[telegram_id] = user
            return user

    async def _ensure_daily_reset(self, telegram_id: int) -> User:
        """Inline daily reset: if usage_reset_date < today, zero counters."""
        user = self._cache.get(telegram_id)
        if user is None:
            user = await self.get_or_create_user(telegram_id)

        today = date.today()
        if user.usage_reset_date >= today:
            return user

        async with async_session() as session:
            await session.execute(
                update(User)
                .where(User.telegram_id == telegram_id, User.usage_reset_date < today)
                .values(tokens_used=0, images_used=0, usage_reset_date=today)
            )
            await session.commit()

        user.tokens_used = 0
        user.images_used = 0
        user.usage_reset_date = today
        self._cache[telegram_id] = user
        return user

    async def check_tokens(self, telegram_id: int, estimated: int = 1000) -> tuple[bool, str | None]:
        """Check if user has token budget. Returns (allowed, error_msg)."""
        user = await self._ensure_daily_reset(telegram_id)
        if user.tokens_limit == 0:  # unlimited
            return True, None
        remaining = user.tokens_limit - user.tokens_used
        if remaining <= 0:
            return False, (
                f"Лимит токенов исчерпан.\n"
                f"Ваш план: <b>{user.plan}</b> ({user.tokens_limit:,} токенов/день).\n"
                f"Обновите план для увеличения лимита."
            )
        return True, None

    async def check_images(self, telegram_id: int) -> tuple[bool, str | None]:
        """Check image generation quota."""
        user = await self._ensure_daily_reset(telegram_id)
        if user.images_limit == 0:  # unlimited
            return True, None
        if user.images_used >= user.images_limit:
            return False, (
                f"Лимит генерации изображений исчерпан.\n"
                f"Ваш план: <b>{user.plan}</b> ({user.images_limit} изображений/день).\n"
                f"Обновите план для увеличения лимита."
            )
        return True, None

    async def check_youtube(self, telegram_id: int) -> tuple[bool, str | None]:
        """Check YouTube download access."""
        user = await self._ensure_daily_reset(telegram_id)
        plan_info = PLAN_LIMITS.get(user.plan, PLAN_LIMITS["free"])
        if not plan_info["youtube_allowed"]:
            return False, (
                f"Скачивание YouTube недоступно.\n"
                f"Ваш план: <b>{user.plan}</b>.\n"
                f"Обновите план для доступа к скачиванию."
            )
        return True, None

    async def track_token_usage(self, telegram_id: int, actual_tokens: int):
        """Track actual token usage after AI call."""
        user = self._cache.get(telegram_id)
        if user is None:
            return

        async with async_session() as session:
            await session.execute(
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(tokens_used=User.tokens_used + actual_tokens)
            )
            await session.commit()

        user.tokens_used += actual_tokens
        self._cache[telegram_id] = user

    async def track_image_usage(self, telegram_id: int):
        """Track image generation usage."""
        user = self._cache.get(telegram_id)
        if user is None:
            return

        async with async_session() as session:
            await session.execute(
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(images_used=User.images_used + 1)
            )
            await session.commit()

        user.images_used += 1
        self._cache[telegram_id] = user

    async def get_usage_info(self, telegram_id: int) -> dict:
        """Get current usage info for /plan command."""
        user = await self._ensure_daily_reset(telegram_id)
        plan_info = PLAN_LIMITS.get(user.plan, PLAN_LIMITS["free"])
        return {
            "plan": user.plan,
            "tokens_used": user.tokens_used,
            "tokens_limit": user.tokens_limit,
            "images_used": user.images_used,
            "images_limit": user.images_limit,
            "youtube_allowed": plan_info["youtube_allowed"],
            "created_at": user.created_at,
            "expires_at": user.expires_at,
        }

    async def set_plan(self, telegram_id: int, plan: str) -> bool:
        """Admin: set user plan. Returns True if successful."""
        if plan not in PLAN_LIMITS:
            return False

        limits = PLAN_LIMITS[plan]

        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            if user is None:
                return False

            user.plan = plan
            user.tokens_limit = limits["tokens_limit"]
            user.images_limit = limits["images_limit"]
            await session.commit()

        # Update cache
        if telegram_id in self._cache:
            self._cache[telegram_id].plan = plan
            self._cache[telegram_id].tokens_limit = limits["tokens_limit"]
            self._cache[telegram_id].images_limit = limits["images_limit"]

        logger.info("Plan set: %s → %s", telegram_id, plan)
        return True
