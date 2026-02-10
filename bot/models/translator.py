"""Translator models: glossary + translation memory + custom prompts."""

from datetime import datetime

from sqlalchemy import Integer, BigInteger, Boolean, Text, String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from bot.database import Base


class TranslatorPrompt(Base):
    """Custom translator system prompt."""
    __tablename__ = "translator_prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TranslatorGlossary(Base):
    """User-defined translation glossary: term_ru ↔ term_ar."""
    __tablename__ = "translator_glossary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("translator_prompts.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    term_ru: Mapped[str] = mapped_column(String(500), index=True)
    term_ar: Mapped[str] = mapped_column(String(500))
    context: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TranslationMemory(Base):
    """Translation memory with pgvector embedding for semantic search."""
    __tablename__ = "translation_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    target_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_lang: Mapped[str] = mapped_column(String(5), nullable=False)  # "ru" / "ar"
    embedding = mapped_column(Vector(1536), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
