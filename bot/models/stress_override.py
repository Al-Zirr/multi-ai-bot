from datetime import datetime

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from bot.database import Base


class StressOverride(Base):
    """Post-russtress corrections: /fix слово правильно."""
    __tablename__ = "stress_overrides"

    id: Mapped[int] = mapped_column(primary_key=True)
    word: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    replacement: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class StressUnknown(Base):
    """Words where russtress failed to place stress — for later review."""
    __tablename__ = "stress_unknowns"

    id: Mapped[int] = mapped_column(primary_key=True)
    word: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    count: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
