from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from bot.database import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    selected_model: Mapped[str] = mapped_column(String(50), default="claude")
    tts_voice: Mapped[str] = mapped_column(String(20), default="onyx")
    response_style: Mapped[str] = mapped_column(String(20), default="medium")
    auto_search: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_memory: Mapped[bool] = mapped_column(Boolean, default=True)
    image_provider: Mapped[str] = mapped_column(String(20), default="dalle")
