"""Translator service: RU ↔ AR translation with glossary and TM."""

import asyncio
import logging
import re

from openai import AsyncOpenAI
from sqlalchemy import select, delete, text

from sqlalchemy.orm import selectinload

from bot.database import async_session
from bot.models.translator import TranslatorGlossary, TranslationMemory, TranslatorPrompt
from bot.services.ai_router import AIRouter, PROVIDERS

logger = logging.getLogger(__name__)

# Question markers — if text looks like a question, answer as AI instead of translating
QUESTION_PREFIXES_RU = (
    "как ", "почему ", "что значит ", "что такое ", "объясни ",
    "в чём разница", "в чем разница", "какой ", "какая ", "какое ",
    "когда ", "сколько ", "зачем ", "можно ли ", "расскажи ",
    "переведи и объясни", "разница между",
)
QUESTION_PREFIXES_AR = (
    "ما ", "ماذا ", "كيف ", "لماذا ", "هل ", "أين ", "متى ", "من ",
    "ما معنى", "ما الفرق", "اشرح ",
)


class TranslatorService:
    def __init__(self, ai_router: AIRouter, openai_api_key: str, embedding_model: str = "text-embedding-3-small"):
        self.ai_router = ai_router
        self.openai_client = AsyncOpenAI(api_key=openai_api_key)
        self.embedding_model = embedding_model

    @staticmethod
    def detect_language(text: str) -> str:
        """Detect language: 'ar' or 'ru'."""
        arabic_count = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
        russian_count = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
        if arabic_count > russian_count:
            return "ar"
        return "ru"

    @staticmethod
    def is_question(text: str) -> bool:
        """Check if text is a question about translation/language rather than text to translate."""
        if "?" in text or "؟" in text:
            return True
        lower = text.lower().strip()
        for prefix in QUESTION_PREFIXES_RU:
            if lower.startswith(prefix):
                return True
        for prefix in QUESTION_PREFIXES_AR:
            if text.strip().startswith(prefix):
                return True
        return False

    def _get_direction(self, text: str, direction: str) -> tuple[str, str]:
        """Return (source_lang, target_lang) based on direction setting."""
        if direction == "ru_ar":
            return "ru", "ar"
        elif direction == "ar_ru":
            return "ar", "ru"
        else:  # auto
            lang = self.detect_language(text)
            if lang == "ar":
                return "ar", "ru"
            return "ru", "ar"

    async def translate(
        self,
        text: str,
        direction: str,
        system_prompt: str,
        provider: str = "claude",
        prompt_id: int | None = None,
    ) -> tuple[str, str]:
        """Translate text. Returns (translation, provider_used)."""
        source_lang, target_lang = self._get_direction(text, direction)

        # Search translation memory for context
        tm_context = await self.search_memory(text)

        # Load glossary (global + prompt-specific)
        glossary = await self.get_glossary(prompt_id=prompt_id)

        # Build messages
        messages = []

        # Add TM context if found
        if tm_context:
            messages.append({
                "role": "user",
                "content": f"Контекст из переводческой памяти:\n{tm_context}",
            })
            messages.append({
                "role": "assistant",
                "content": "Понял, учту эти переводы как референс.",
            })

        lang_label = "арабский" if target_lang == "ar" else "русский"
        messages.append({
            "role": "user",
            "content": f"Переведи на {lang_label}:\n\n{text}",
        })

        # Build full system prompt with glossary
        full_prompt = system_prompt
        if glossary:
            glossary_text = "\n".join(f"• {ru} = {ar}" for ru, ar in glossary)
            full_prompt += f"\n\nГлоссарий (используй эти переводы терминов):\n{glossary_text}"

        service = self.ai_router.get_service(provider)
        translation = await service.generate(messages, system_prompt=full_prompt)

        # Save to translation memory
        await self.save_to_memory(text, translation, source_lang)

        return translation, provider

    async def translate_remaining(
        self,
        text: str,
        direction: str,
        system_prompt: str,
        exclude_provider: str,
        prompt_id: int | None = None,
    ) -> dict[str, str]:
        """Translate with all models except excluded one. Returns {provider: translation}."""
        source_lang, target_lang = self._get_direction(text, direction)
        lang_label = "арабский" if target_lang == "ar" else "русский"

        glossary = await self.get_glossary(prompt_id=prompt_id)
        full_prompt = system_prompt
        if glossary:
            glossary_text = "\n".join(f"• {ru} = {ar}" for ru, ar in glossary)
            full_prompt += f"\n\nГлоссарий (используй эти переводы терминов):\n{glossary_text}"

        messages = [{
            "role": "user",
            "content": f"Переведи на {lang_label}:\n\n{text}",
        }]

        results = {}
        providers = [p for p in self.ai_router.services.keys() if p != exclude_provider]

        async def _translate_one(provider: str):
            try:
                service = self.ai_router.get_service(provider)
                result = await service.generate(messages, system_prompt=full_prompt)
                results[provider] = result
            except Exception as e:
                logger.exception("Compare translate failed for %s", provider)
                results[provider] = f"[Ошибка: {str(e)[:100]}]"

        await asyncio.gather(*[_translate_one(p) for p in providers])
        return results

    # ═══════════════════════════════════════════════════════
    #  TRANSLATION MEMORY (pgvector)
    # ═══════════════════════════════════════════════════════

    async def _get_embedding(self, text: str) -> list[float]:
        response = await self.openai_client.embeddings.create(
            model=self.embedding_model,
            input=text,
        )
        return response.data[0].embedding

    async def search_memory(self, source_text: str, top_k: int = 3) -> str | None:
        """Search translation memory for similar past translations."""
        try:
            embedding = await self._get_embedding(source_text)
            emb_str = "[" + ",".join(str(x) for x in embedding) + "]"

            async with async_session() as session:
                sql = text("""
                    SELECT source_text, target_text, source_lang,
                           1 - (embedding <=> :emb::vector) as score
                    FROM translation_memory
                    ORDER BY embedding <=> :emb::vector
                    LIMIT :k
                """)
                result = await session.execute(sql, {"emb": emb_str, "k": top_k})
                rows = result.fetchall()

            if not rows:
                return None

            parts = []
            for row in rows:
                score = float(row[3])
                if score < 0.7:
                    continue
                src, tgt, lang = row[0], row[1], row[2]
                src_label = "RU" if lang == "ru" else "AR"
                tgt_label = "AR" if lang == "ru" else "RU"
                parts.append(f"[{src_label}] {src}\n[{tgt_label}] {tgt} (совпадение: {score:.0%})")

            return "\n\n".join(parts) if parts else None

        except Exception:
            logger.exception("TM search failed")
            return None

    async def save_to_memory(self, source_text: str, target_text: str, source_lang: str):
        """Save translation pair to memory with embedding."""
        try:
            embedding = await self._get_embedding(source_text)
            async with async_session() as session:
                session.add(TranslationMemory(
                    source_text=source_text,
                    target_text=target_text,
                    source_lang=source_lang,
                    embedding=embedding,
                ))
                await session.commit()
            logger.info("TM saved: %s... → %s...", source_text[:30], target_text[:30])
        except Exception:
            logger.exception("Failed to save to TM")

    # ═══════════════════════════════════════════════════════
    #  GLOSSARY CRUD
    # ═══════════════════════════════════════════════════════

    async def get_glossary(self, prompt_id: int | None = None) -> list[tuple[str, str]]:
        """Get glossary entries. Global (prompt_id=None) + prompt-specific if set."""
        try:
            async with async_session() as session:
                # Always load global glossary (prompt_id IS NULL)
                stmt = select(TranslatorGlossary).where(
                    TranslatorGlossary.prompt_id.is_(None)
                )
                result = await session.execute(stmt)
                entries = [(r.term_ru, r.term_ar) for r in result.scalars().all()]

                # Also load prompt-specific glossary if active
                if prompt_id:
                    stmt2 = select(TranslatorGlossary).where(
                        TranslatorGlossary.prompt_id == prompt_id
                    )
                    result2 = await session.execute(stmt2)
                    entries.extend((r.term_ru, r.term_ar) for r in result2.scalars().all())

                return entries
        except Exception:
            logger.exception("Failed to load glossary")
            return []

    async def add_glossary(
        self, term_ru: str, term_ar: str,
        context: str | None = None, prompt_id: int | None = None,
    ) -> bool:
        """Add or update glossary entry."""
        try:
            async with async_session() as session:
                stmt = select(TranslatorGlossary).where(
                    TranslatorGlossary.term_ru == term_ru.lower(),
                    TranslatorGlossary.prompt_id == prompt_id if prompt_id else TranslatorGlossary.prompt_id.is_(None),
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()
                if existing:
                    existing.term_ar = term_ar
                    existing.context = context
                else:
                    session.add(TranslatorGlossary(
                        term_ru=term_ru.lower(),
                        term_ar=term_ar,
                        context=context,
                        prompt_id=prompt_id,
                    ))
                await session.commit()
            logger.info("Glossary: '%s' = '%s' (prompt_id=%s)", term_ru, term_ar, prompt_id)
            return True
        except Exception:
            logger.exception("Failed to add glossary entry")
            return False

    async def remove_glossary(self, term_ru: str) -> bool:
        """Remove glossary entry (global only)."""
        try:
            async with async_session() as session:
                stmt = delete(TranslatorGlossary).where(
                    TranslatorGlossary.term_ru == term_ru.lower(),
                    TranslatorGlossary.prompt_id.is_(None),
                )
                result = await session.execute(stmt)
                await session.commit()
            return result.rowcount > 0
        except Exception:
            logger.exception("Failed to remove glossary entry")
            return False

    # ═══════════════════════════════════════════════════════
    #  CUSTOM PROMPTS
    # ═══════════════════════════════════════════════════════

    async def get_prompts(self, user_id: int) -> list[TranslatorPrompt]:
        """Get all custom prompts for user."""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(TranslatorPrompt)
                    .where(TranslatorPrompt.user_id == user_id)
                    .order_by(TranslatorPrompt.id)
                )
                return list(result.scalars().all())
        except Exception:
            logger.exception("Failed to get prompts")
            return []

    async def get_active_prompt(self, user_id: int) -> TranslatorPrompt | None:
        """Get the currently active custom prompt."""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(TranslatorPrompt).where(
                        TranslatorPrompt.user_id == user_id,
                        TranslatorPrompt.is_active == True,  # noqa: E712
                    )
                )
                return result.scalar_one_or_none()
        except Exception:
            logger.exception("Failed to get active prompt")
            return None

    async def add_prompt(self, user_id: int, name: str, system_prompt: str) -> int | None:
        """Add a custom prompt. Returns prompt ID."""
        try:
            async with async_session() as session:
                prompt = TranslatorPrompt(
                    user_id=user_id, name=name,
                    system_prompt=system_prompt, is_active=False,
                )
                session.add(prompt)
                await session.commit()
                await session.refresh(prompt)
                logger.info("Prompt added: '%s' (id=%d)", name, prompt.id)
                return prompt.id
        except Exception:
            logger.exception("Failed to add prompt")
            return None

    async def activate_prompt(self, user_id: int, name: str) -> bool:
        """Activate a prompt by name, deactivate others."""
        try:
            async with async_session() as session:
                # Deactivate all
                all_prompts = await session.execute(
                    select(TranslatorPrompt).where(TranslatorPrompt.user_id == user_id)
                )
                for p in all_prompts.scalars().all():
                    p.is_active = False

                # Activate by name
                result = await session.execute(
                    select(TranslatorPrompt).where(
                        TranslatorPrompt.user_id == user_id,
                        TranslatorPrompt.name == name,
                    )
                )
                prompt = result.scalar_one_or_none()
                if not prompt:
                    return False
                prompt.is_active = True
                await session.commit()
                logger.info("Prompt activated: '%s'", name)
                return True
        except Exception:
            logger.exception("Failed to activate prompt")
            return False

    async def deactivate_all_prompts(self, user_id: int):
        """Deactivate all custom prompts — use standard."""
        try:
            async with async_session() as session:
                all_prompts = await session.execute(
                    select(TranslatorPrompt).where(TranslatorPrompt.user_id == user_id)
                )
                for p in all_prompts.scalars().all():
                    p.is_active = False
                await session.commit()
        except Exception:
            logger.exception("Failed to deactivate prompts")

    async def delete_prompt(self, user_id: int, name: str) -> bool:
        """Delete a prompt and its glossary entries."""
        try:
            async with async_session() as session:
                result = await session.execute(
                    delete(TranslatorPrompt).where(
                        TranslatorPrompt.user_id == user_id,
                        TranslatorPrompt.name == name,
                    )
                )
                await session.commit()
            return result.rowcount > 0
        except Exception:
            logger.exception("Failed to delete prompt")
            return False
