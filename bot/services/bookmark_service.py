"""Bookmark service: save, search, delete AI responses."""

import logging
from sqlalchemy import select, func, delete, update

from bot.database import async_session
from bot.models.bookmark import Bookmark

logger = logging.getLogger(__name__)

PAGE_SIZE = 10


def _make_preview(text: str, max_len: int = 100) -> str:
    """First ~100 chars, cut at word boundary."""
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    last_space = truncated.rfind(" ")
    if last_space > max_len // 2:
        truncated = truncated[:last_space]
    return truncated + "..."


class BookmarkService:

    async def add(self, user_id: int, message_text: str, model: str | None = None) -> Bookmark:
        preview = _make_preview(message_text)
        bm = Bookmark(
            user_id=user_id,
            message_text=message_text,
            model=model,
            preview=preview,
        )
        async with async_session() as session:
            session.add(bm)
            await session.commit()
            await session.refresh(bm)
            return bm

    async def add_note(self, bookmark_id: int, note: str) -> bool:
        async with async_session() as session:
            result = await session.execute(
                update(Bookmark).where(Bookmark.id == bookmark_id).values(note=note)
            )
            await session.commit()
            return result.rowcount > 0

    async def get_all(self, user_id: int, page: int = 0) -> tuple[list[Bookmark], int]:
        """Returns (bookmarks, total_count) for page."""
        async with async_session() as session:
            total = await session.scalar(
                select(func.count(Bookmark.id)).where(Bookmark.user_id == user_id)
            )
            rows = await session.execute(
                select(Bookmark)
                .where(Bookmark.user_id == user_id)
                .order_by(Bookmark.created_at.desc())
                .offset(page * PAGE_SIZE)
                .limit(PAGE_SIZE)
            )
            bookmarks = list(rows.scalars().all())
            return bookmarks, total or 0

    async def get_by_id(self, bookmark_id: int) -> Bookmark | None:
        async with async_session() as session:
            return await session.get(Bookmark, bookmark_id)

    async def search(self, user_id: int, query: str) -> list[Bookmark]:
        pattern = f"%{query}%"
        async with async_session() as session:
            rows = await session.execute(
                select(Bookmark)
                .where(
                    Bookmark.user_id == user_id,
                    (Bookmark.message_text.ilike(pattern)) | (Bookmark.note.ilike(pattern)),
                )
                .order_by(Bookmark.created_at.desc())
                .limit(50)
            )
            return list(rows.scalars().all())

    async def delete(self, bookmark_id: int) -> bool:
        async with async_session() as session:
            result = await session.execute(
                delete(Bookmark).where(Bookmark.id == bookmark_id)
            )
            await session.commit()
            return result.rowcount > 0

    async def count(self, user_id: int) -> int:
        async with async_session() as session:
            return await session.scalar(
                select(func.count(Bookmark.id)).where(Bookmark.user_id == user_id)
            ) or 0
