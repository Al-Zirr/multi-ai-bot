"""Memory service: store and retrieve user facts."""

import json
import logging
import re
import time
from datetime import datetime

from openai import AsyncOpenAI
from sqlalchemy import select, delete, update, func as sa_func

from bot.database import async_session
from bot.models.memory import UserMemory, MemoryCategory

logger = logging.getLogger(__name__)

# Default categories (for new users)
DEFAULT_CATEGORIES = [
    ("personal", "Личное", "👤"),
    ("work", "Работа", "💼"),
    ("fiqh", "Фикх", "📖"),
    ("aqeedah", "Акыда", "🕌"),
    ("mantiq", "Мантык", "🧠"),
    ("tasawwuf", "Тасаввуф", "📚"),
    ("language", "Язык", "🌍"),
    ("preferences", "Предпочтения", "⚙️"),
]

# Markers that suggest user is sharing personal info
_PERSONAL_MARKERS = re.compile(
    r"\b(я |меня |мне |мой |моя |моё |мои |моих |моим |моей |"
    r"зовут |живу |работаю |учусь |люблю |предпочитаю |"
    r"нравится |хочу |умею |знаю |изучаю |верю |"
    r"мой мазхаб|я ханафит|я шафиит|я маликит|я ханбалит)",
    re.IGNORECASE,
)

# Extraction prompt
MEMORY_EXTRACT_PROMPT = (
    "Ты анализируешь сообщение пользователя и извлекаешь из него факты о пользователе.\n"
    "Верни JSON-массив фактов. Каждый факт:\n"
    '{"category": "<slug>", "fact": "<краткий факт>"}\n\n'
    "Доступные категории:\n"
    "{categories}\n\n"
    "Правила:\n"
    "- Извлекай только ЯВНЫЕ факты о самом пользователе\n"
    "- Не извлекай общие знания или вопросы\n"
    "- Факт должен быть кратким (1 предложение)\n"
    "- Если фактов нет — верни []\n"
    "- Верни ТОЛЬКО JSON, без markdown и пояснений\n\n"
    "Сообщение пользователя:\n{text}"
)


class MemoryService:
    def __init__(self, openai_client: AsyncOpenAI):
        self.openai_client = openai_client
        # Cooldown: user_id -> last_extract_time
        self._extract_cooldown: dict[int, float] = {}
        # Cache: user_id -> list of categories
        self._categories_cache: dict[int, list[dict]] = {}

    # ═══════════════════════════════════════════════════════
    #  CATEGORIES
    # ═══════════════════════════════════════════════════════

    async def get_categories(self, user_id: int) -> list[dict]:
        """Get all categories for user. Init defaults if none exist."""
        if user_id in self._categories_cache:
            return self._categories_cache[user_id]

        try:
            async with async_session() as session:
                result = await session.execute(
                    select(MemoryCategory)
                    .where(MemoryCategory.user_id == user_id)
                    .order_by(MemoryCategory.id)
                )
                rows = result.scalars().all()

                if not rows:
                    # Init default categories
                    for slug, label, emoji in DEFAULT_CATEGORIES:
                        session.add(MemoryCategory(
                            user_id=user_id, slug=slug, label=label,
                            emoji=emoji, is_default=True,
                        ))
                    await session.commit()
                    # Re-query
                    result = await session.execute(
                        select(MemoryCategory)
                        .where(MemoryCategory.user_id == user_id)
                        .order_by(MemoryCategory.id)
                    )
                    rows = result.scalars().all()

                cats = [
                    {"slug": r.slug, "label": r.label, "emoji": r.emoji, "is_default": r.is_default}
                    for r in rows
                ]
                self._categories_cache[user_id] = cats
                return cats
        except Exception:
            logger.exception("Failed to load memory categories")
            return [{"slug": s, "label": l, "emoji": e, "is_default": True} for s, l, e in DEFAULT_CATEGORIES]

    def get_category_emoji(self, categories: list[dict], slug: str) -> str:
        for cat in categories:
            if cat["slug"] == slug:
                return cat["emoji"]
        return "📌"

    def get_category_label(self, categories: list[dict], slug: str) -> str:
        for cat in categories:
            if cat["slug"] == slug:
                return cat["label"]
        return slug

    async def add_category(self, user_id: int, slug: str, emoji: str, label: str) -> bool:
        try:
            async with async_session() as session:
                # Check if exists
                result = await session.execute(
                    select(MemoryCategory).where(
                        MemoryCategory.user_id == user_id,
                        MemoryCategory.slug == slug,
                    )
                )
                if result.scalar_one_or_none():
                    return False
                session.add(MemoryCategory(
                    user_id=user_id, slug=slug, label=label,
                    emoji=emoji, is_default=False,
                ))
                await session.commit()
            self._categories_cache.pop(user_id, None)
            return True
        except Exception:
            logger.exception("Failed to add category")
            return False

    # ═══════════════════════════════════════════════════════
    #  MEMORY CRUD
    # ═══════════════════════════════════════════════════════

    async def add_memory(
        self, user_id: int, category: str, content: str,
        source: str = "manual", confirmed: bool = True,
    ) -> int | None:
        """Add a memory fact. Returns memory ID."""
        try:
            async with async_session() as session:
                mem = UserMemory(
                    user_id=user_id, category=category, content=content,
                    source=source, confirmed=confirmed,
                )
                session.add(mem)
                await session.commit()
                await session.refresh(mem)
                logger.info("Memory added: [%s] %s (id=%d)", category, content[:50], mem.id)
                return mem.id
        except Exception:
            logger.exception("Failed to add memory")
            return None

    async def confirm_memory(self, memory_id: int) -> bool:
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(UserMemory).where(UserMemory.id == memory_id)
                )
                mem = result.scalar_one_or_none()
                if mem:
                    mem.confirmed = True
                    await session.commit()
                    return True
            return False
        except Exception:
            logger.exception("Failed to confirm memory")
            return False

    async def reject_memory(self, memory_id: int) -> bool:
        try:
            async with async_session() as session:
                await session.execute(
                    delete(UserMemory).where(UserMemory.id == memory_id)
                )
                await session.commit()
            return True
        except Exception:
            logger.exception("Failed to reject memory")
            return False

    async def remove_memory(self, memory_id: int, user_id: int) -> bool:
        try:
            async with async_session() as session:
                result = await session.execute(
                    delete(UserMemory).where(
                        UserMemory.id == memory_id,
                        UserMemory.user_id == user_id,
                    )
                )
                await session.commit()
            return result.rowcount > 0
        except Exception:
            logger.exception("Failed to remove memory")
            return False

    async def clear_memories(self, user_id: int) -> int:
        try:
            async with async_session() as session:
                result = await session.execute(
                    delete(UserMemory).where(UserMemory.user_id == user_id)
                )
                await session.commit()
            return result.rowcount
        except Exception:
            logger.exception("Failed to clear memories")
            return 0

    # ═══════════════════════════════════════════════════════
    #  RETRIEVAL
    # ═══════════════════════════════════════════════════════

    async def get_confirmed_memories(self, user_id: int) -> list[UserMemory]:
        """Get all confirmed memories for user."""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(UserMemory).where(
                        UserMemory.user_id == user_id,
                        UserMemory.confirmed == True,  # noqa: E712
                    ).order_by(UserMemory.category, UserMemory.id)
                )
                return list(result.scalars().all())
        except Exception:
            logger.exception("Failed to get memories")
            return []

    async def get_all_memories(self, user_id: int) -> list[UserMemory]:
        """Get all memories (including unconfirmed) for user."""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(UserMemory).where(
                        UserMemory.user_id == user_id,
                    ).order_by(UserMemory.category, UserMemory.id)
                )
                return list(result.scalars().all())
        except Exception:
            logger.exception("Failed to get all memories")
            return []

    async def get_pending_memories(self, user_id: int) -> list[UserMemory]:
        """Get unconfirmed auto-extracted memories."""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(UserMemory).where(
                        UserMemory.user_id == user_id,
                        UserMemory.confirmed == False,  # noqa: E712
                    ).order_by(UserMemory.id)
                )
                return list(result.scalars().all())
        except Exception:
            logger.exception("Failed to get pending memories")
            return []

    # ═══════════════════════════════════════════════════════
    #  FORMAT FOR PROMPT
    # ═══════════════════════════════════════════════════════

    async def format_for_prompt(self, user_id: int) -> str | None:
        """Format confirmed memories as a block for system prompt. Returns None if empty."""
        memories = await self.get_confirmed_memories(user_id)
        if not memories:
            return None

        categories = await self.get_categories(user_id)

        # Group by category
        grouped: dict[str, list[str]] = {}
        memory_ids: list[int] = []
        for mem in memories:
            if mem.category not in grouped:
                grouped[mem.category] = []
            grouped[mem.category].append(mem.content)
            memory_ids.append(mem.id)

        lines = ["Что ты знаешь о пользователе:"]
        for cat_slug, facts in grouped.items():
            emoji = self.get_category_emoji(categories, cat_slug)
            label = self.get_category_label(categories, cat_slug)
            facts_str = ". ".join(facts)
            lines.append(f"{emoji} {label}: {facts_str}")

        # Increment usage counters
        await self._increment_usage(memory_ids)

        return "\n".join(lines)

    async def _increment_usage(self, memory_ids: list[int]):
        if not memory_ids:
            return
        try:
            async with async_session() as session:
                await session.execute(
                    update(UserMemory)
                    .where(UserMemory.id.in_(memory_ids))
                    .values(
                        times_used=UserMemory.times_used + 1,
                        last_used_at=sa_func.now(),
                    )
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to increment memory usage")

    # ═══════════════════════════════════════════════════════
    #  FORMAT FOR DISPLAY
    # ═══════════════════════════════════════════════════════

    async def format_for_display(self, user_id: int) -> str:
        """Format memories for the Память button / /memory command."""
        memories = await self.get_confirmed_memories(user_id)
        if not memories:
            return (
                "<b>Память пуста</b>\n\n"
                "Добавьте факт: /memory add personal Меня зовут ..."
            )

        categories = await self.get_categories(user_id)

        # Group by category
        grouped: dict[str, list[UserMemory]] = {}
        for mem in memories:
            if mem.category not in grouped:
                grouped[mem.category] = []
            grouped[mem.category].append(mem)

        lines = [f"<b>Память</b> ({len(memories)} фактов)\n"]
        idx = 1
        for cat_slug, mems in grouped.items():
            emoji = self.get_category_emoji(categories, cat_slug)
            label = self.get_category_label(categories, cat_slug)
            lines.append(f"\n{emoji} <b>{label}:</b>")
            for mem in mems:
                date_str = mem.created_at.strftime("%d.%m") if mem.created_at else ""
                used_str = f"×{mem.times_used}" if mem.times_used > 0 else "новый"
                lines.append(f"  {idx}. {mem.content} <i>({used_str}, {date_str})</i> [id:{mem.id}]")
                idx += 1

        return "\n".join(lines)

    # ═══════════════════════════════════════════════════════
    #  AUTO-EXTRACTION
    # ═══════════════════════════════════════════════════════

    def should_extract(self, text: str, user_id: int) -> bool:
        """Heuristic: should we try to extract facts from this message?"""
        if len(text) < 15:
            return False
        if not _PERSONAL_MARKERS.search(text):
            return False
        # Cooldown: max 1 extraction per 5 messages (tracked by time, ~30s min gap)
        last = self._extract_cooldown.get(user_id, 0)
        if time.time() - last < 30:
            return False
        return True

    async def extract_facts(self, text: str, user_id: int) -> list[dict]:
        """Use GPT to extract facts from user message. Returns list of {category, fact}."""
        categories = await self.get_categories(user_id)
        cats_str = "\n".join(f"- {c['slug']} ({c['emoji']} {c['label']})" for c in categories)

        prompt = MEMORY_EXTRACT_PROMPT.format(categories=cats_str, text=text)

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=500,
            )
            content = response.choices[0].message.content.strip()

            # Parse JSON
            # Strip markdown code fences if present
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

            facts = json.loads(content)
            if not isinstance(facts, list):
                return []

            # Validate categories
            valid_slugs = {c["slug"] for c in categories}
            valid_facts = []
            for fact in facts:
                if isinstance(fact, dict) and "category" in fact and "fact" in fact:
                    if fact["category"] in valid_slugs and len(fact["fact"].strip()) > 2:
                        valid_facts.append(fact)

            self._extract_cooldown[user_id] = time.time()
            logger.info("Extracted %d facts from user message", len(valid_facts))
            return valid_facts

        except Exception:
            logger.exception("Failed to extract facts")
            return []

    async def save_extracted_facts(self, user_id: int, facts: list[dict]) -> list[int]:
        """Save extracted facts as unconfirmed. Returns list of memory IDs."""
        ids = []
        for fact in facts:
            mem_id = await self.add_memory(
                user_id=user_id,
                category=fact["category"],
                content=fact["fact"],
                source="auto",
                confirmed=False,
            )
            if mem_id:
                ids.append(mem_id)
        return ids
