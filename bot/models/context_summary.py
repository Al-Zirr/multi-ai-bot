from datetime import datetime

from sqlalchemy import BigInteger, Integer, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from bot.database import Base


class ContextSummary(Base):
    __tablename__ = "context_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    messages_from: Mapped[int] = mapped_column(Integer, nullable=False)
    messages_to: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_saved: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
