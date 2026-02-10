from datetime import date, datetime

from sqlalchemy import BigInteger, Integer, String, Date, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from bot.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    plan: Mapped[str] = mapped_column(String(20), nullable=False, default="free")

    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=10_000)
    images_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    images_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    usage_reset_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
