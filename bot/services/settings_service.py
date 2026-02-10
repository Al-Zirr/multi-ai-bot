"""Per-user settings: CRUD + in-memory cache."""

import logging
from dataclasses import dataclass

from sqlalchemy import select

from bot.database import async_session
from bot.models.user_settings import UserSettings

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude"
DEFAULT_VOICE = "onyx"
DEFAULT_STYLE = "medium"
DEFAULT_AUTO_SEARCH = True
DEFAULT_AUTO_MEMORY = True
DEFAULT_IMAGE_PROVIDER = "dalle"


@dataclass
class UserSettingsDTO:
    selected_model: str = DEFAULT_MODEL
    tts_voice: str = DEFAULT_VOICE
    response_style: str = DEFAULT_STYLE
    auto_search: bool = DEFAULT_AUTO_SEARCH
    auto_memory: bool = DEFAULT_AUTO_MEMORY
    image_provider: str = DEFAULT_IMAGE_PROVIDER


class SettingsService:
    def __init__(self):
        self._cache: dict[int, UserSettingsDTO] = {}

    async def get(self, user_id: int) -> UserSettingsDTO:
        if user_id in self._cache:
            return self._cache[user_id]
        try:
            async with async_session() as session:
                stmt = select(UserSettings).where(UserSettings.user_id == user_id)
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()
                if row:
                    dto = UserSettingsDTO(
                        selected_model=row.selected_model or DEFAULT_MODEL,
                        tts_voice=row.tts_voice or DEFAULT_VOICE,
                        response_style=row.response_style or DEFAULT_STYLE,
                        auto_search=row.auto_search if row.auto_search is not None else DEFAULT_AUTO_SEARCH,
                        auto_memory=row.auto_memory if row.auto_memory is not None else DEFAULT_AUTO_MEMORY,
                        image_provider=row.image_provider or DEFAULT_IMAGE_PROVIDER,
                    )
                else:
                    dto = UserSettingsDTO()
                self._cache[user_id] = dto
                return dto
        except Exception:
            logger.exception("Failed to load settings for user %d", user_id)
            return UserSettingsDTO()

    async def update(self, user_id: int, **kwargs) -> UserSettingsDTO:
        dto = await self.get(user_id)
        for key, value in kwargs.items():
            if hasattr(dto, key):
                setattr(dto, key, value)

        try:
            async with async_session() as session:
                stmt = select(UserSettings).where(UserSettings.user_id == user_id)
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()
                if row:
                    for key, value in kwargs.items():
                        if hasattr(row, key):
                            setattr(row, key, value)
                else:
                    row = UserSettings(
                        user_id=user_id,
                        selected_model=dto.selected_model,
                        tts_voice=dto.tts_voice,
                        response_style=dto.response_style,
                        auto_search=dto.auto_search,
                        auto_memory=dto.auto_memory,
                        image_provider=dto.image_provider,
                    )
                    session.add(row)
                await session.commit()
        except Exception:
            logger.exception("Failed to update settings for user %d", user_id)

        self._cache[user_id] = dto
        return dto
