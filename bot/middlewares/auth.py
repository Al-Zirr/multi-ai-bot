import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    def __init__(self, admin_ids: list[int], quota_service=None):
        self.admin_ids = admin_ids
        self.quota_service = quota_service

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = None
        username = None
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
            username = event.from_user.username if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
            username = event.from_user.username if event.from_user else None

        if user_id is None:
            return

        if self.admin_ids and user_id not in self.admin_ids:
            logger.warning("Unauthorized access attempt: user_id=%s", user_id)
            if isinstance(event, Message):
                await event.answer("Доступ запрещён")
            elif isinstance(event, CallbackQuery):
                await event.answer("Доступ запрещён", show_alert=True)
            return

        # Auto-register user in quota system
        if self.quota_service:
            await self.quota_service.get_or_create_user(user_id, username)

        return await handler(event, data)
