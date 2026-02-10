import logging

from sqlalchemy import select, func, delete

from bot.database import async_session
from bot.models.conversation import Conversation
from bot.models.context_summary import ContextSummary

logger = logging.getLogger(__name__)

SUMMARY_PROMPT = (
    "Сожми следующий диалог в краткое резюме (2-4 предложения). "
    "Сохрани ключевые факты, решения и контекст. Пиши на том же языке, "
    "что и диалог. Отвечай только резюме, без вводных слов.\n\n"
)


class ContextService:
    def __init__(self, max_context: int = 20):
        self.max_context = max_context

    async def add_message(
        self, user_id: int, role: str, content: str, model: str | None = None
    ) -> None:
        async with async_session() as session:
            msg = Conversation(
                user_id=user_id, role=role, content=content, model=model
            )
            session.add(msg)
            await session.commit()

    async def get_history(self, user_id: int) -> list[dict[str, str]]:
        """Get last N messages for user."""
        async with async_session() as session:
            stmt = (
                select(Conversation)
                .where(Conversation.user_id == user_id)
                .order_by(Conversation.id.desc())
                .limit(self.max_context)
            )
            result = await session.execute(stmt)
            rows = list(result.scalars().all())

        # Reverse to chronological order
        rows.reverse()
        return [{"role": r.role, "content": r.content} for r in rows]

    async def get_context_for_ai(
        self, user_id: int, ai_service=None
    ) -> list[dict[str, str]]:
        """Build context: summaries + recent messages.

        If there are summaries, prepend them as system context.
        If message count exceeds threshold and ai_service provided,
        trigger compression of older messages.
        """
        messages = []

        # Load summaries
        async with async_session() as session:
            stmt = (
                select(ContextSummary)
                .where(ContextSummary.user_id == user_id)
                .order_by(ContextSummary.id.asc())
            )
            result = await session.execute(stmt)
            summaries = result.scalars().all()

        if summaries:
            summary_text = "\n".join(s.summary for s in summaries)
            messages.append({
                "role": "user",
                "content": f"[Краткое содержание предыдущего диалога]\n{summary_text}",
            })
            messages.append({
                "role": "assistant",
                "content": "Понял, учитываю контекст предыдущего диалога.",
            })

        # Load recent messages
        history = await self.get_history(user_id)
        messages.extend(history)

        # Check if compression needed
        total = await self._count_messages(user_id)
        if total > self.max_context * 2 and ai_service:
            await self._compress_old_messages(user_id, ai_service)

        return messages

    async def clear_history(self, user_id: int) -> int:
        """Delete all messages and summaries for user. Returns deleted count."""
        async with async_session() as session:
            count_stmt = select(func.count()).where(Conversation.user_id == user_id)
            result = await session.execute(count_stmt)
            count = result.scalar() or 0

            await session.execute(
                delete(Conversation).where(Conversation.user_id == user_id)
            )
            await session.execute(
                delete(ContextSummary).where(ContextSummary.user_id == user_id)
            )
            await session.commit()
        return count

    async def get_stats(self, user_id: int) -> dict:
        """Get context statistics for /context command."""
        async with async_session() as session:
            # Total messages
            msg_count = await session.execute(
                select(func.count()).where(Conversation.user_id == user_id)
            )
            total_messages = msg_count.scalar() or 0

            # Summaries count
            sum_count = await session.execute(
                select(func.count()).where(ContextSummary.user_id == user_id)
            )
            total_summaries = sum_count.scalar() or 0

            # Tokens saved
            tokens_stmt = select(func.coalesce(func.sum(ContextSummary.tokens_saved), 0)).where(
                ContextSummary.user_id == user_id
            )
            tokens_result = await session.execute(tokens_stmt)
            tokens_saved = tokens_result.scalar() or 0

        return {
            "total_messages": total_messages,
            "context_window": min(total_messages, self.max_context),
            "summaries": total_summaries,
            "tokens_saved": tokens_saved,
        }

    async def _count_messages(self, user_id: int) -> int:
        async with async_session() as session:
            result = await session.execute(
                select(func.count()).where(Conversation.user_id == user_id)
            )
            return result.scalar() or 0

    async def _compress_old_messages(self, user_id: int, ai_service) -> None:
        """Summarize old messages beyond the context window."""
        try:
            async with async_session() as session:
                # Get all messages except last max_context
                total = await self._count_messages(user_id)
                to_compress = total - self.max_context

                if to_compress <= 0:
                    return

                stmt = (
                    select(Conversation)
                    .where(Conversation.user_id == user_id)
                    .order_by(Conversation.id.asc())
                    .limit(to_compress)
                )
                result = await session.execute(stmt)
                old_messages = result.scalars().all()

                if not old_messages:
                    return

                # Build text for summarization
                dialog_lines = []
                for msg in old_messages:
                    role_label = "Пользователь" if msg.role == "user" else "Ассистент"
                    dialog_lines.append(f"{role_label}: {msg.content}")
                dialog_text = "\n".join(dialog_lines)

                # Summarize using AI
                summary_messages = [
                    {"role": "user", "content": SUMMARY_PROMPT + dialog_text}
                ]
                summary = await ai_service.generate(summary_messages)

                if summary:
                    # Save summary
                    cs = ContextSummary(
                        user_id=user_id,
                        summary=summary,
                        messages_from=old_messages[0].id,
                        messages_to=old_messages[-1].id,
                        tokens_saved=len(dialog_text) // 4,  # rough estimate
                    )
                    session.add(cs)

                    # Delete compressed messages
                    old_ids = [m.id for m in old_messages]
                    await session.execute(
                        delete(Conversation).where(Conversation.id.in_(old_ids))
                    )
                    await session.commit()
                    logger.info(
                        "Compressed %d messages for user %d", len(old_ids), user_id
                    )

        except Exception:
            logger.exception("Failed to compress context for user %d", user_id)
