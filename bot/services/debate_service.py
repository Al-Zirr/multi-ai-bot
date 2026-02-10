import asyncio
import logging
import time

from bot.services.ai_router import AIRouter
from bot.utils.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

DEBATE_PROMPT = (
    "Ты участвуешь в экспертной дискуссии. Вот вопрос пользователя "
    "и ответы других AI-моделей.\n\n"
    "Вопрос: {question}\n\n"
    "{other_answers}\n\n"
    "Проанализируй ответы коллег:\n"
    "1. С чем ты согласен и почему\n"
    "2. С чем не согласен и почему\n"
    "3. Что важное они упустили\n"
    "4. Твоя итоговая позиция\n\n"
    "Будь конкретен, ссылайся на аргументы коллег. "
    "Не будь вежливым ради вежливости — будь честным."
)

SUMMARY_PROMPT = (
    "Вот вопрос пользователя, ответы трёх AI-моделей и их критические разборы.\n\n"
    "Вопрос: {question}\n\n"
    "{all_content}\n\n"
    "Составь финальное резюме:\n"
    "- Консенсус: в чём все согласны\n"
    "- Разногласия: ключевые спорные моменты\n"
    "- Лучшая рекомендация: синтез лучших идей из всех ответов"
)


class DebateService:
    def __init__(self, ai_router: AIRouter):
        self.ai_router = ai_router

    async def get_initial_answers(
        self, question: str
    ) -> dict[str, tuple[str, float]]:
        """Get answers from all models. Returns {provider: (answer, elapsed)}."""
        providers = self.ai_router.available_providers()
        messages = [{"role": "user", "content": question}]

        async def _ask(prov: str) -> tuple[str, str, float]:
            svc = self.ai_router.get_service(prov)
            start = time.monotonic()
            try:
                result = await svc.generate(messages, system_prompt=SYSTEM_PROMPT)
                elapsed = time.monotonic() - start
                return prov, result, elapsed
            except Exception as e:
                elapsed = time.monotonic() - start
                return prov, f"Ошибка: {e}", elapsed

        results = await asyncio.gather(*[_ask(p) for p in providers])
        return {prov: (answer, elapsed) for prov, answer, elapsed in results}

    async def run_debate_round(
        self, question: str, answers: dict[str, tuple[str, float]]
    ) -> dict[str, tuple[str, float]]:
        """Each model critiques the others. Returns {provider: (critique, elapsed)}."""
        providers = list(answers.keys())

        async def _critique(prov: str) -> tuple[str, str, float]:
            svc = self.ai_router.get_service(prov)
            display = self.ai_router.get_display_name(prov)

            # Build other answers text
            other_parts = []
            for other_prov, (answer, _) in answers.items():
                if other_prov == prov:
                    continue
                other_display = self.ai_router.get_display_name(other_prov)
                other_parts.append(f"Ответ {other_display}:\n{answer}")

            other_text = "\n\n".join(other_parts)
            prompt = DEBATE_PROMPT.format(question=question, other_answers=other_text)

            messages = [{"role": "user", "content": prompt}]
            start = time.monotonic()
            try:
                result = await svc.generate(messages)
                elapsed = time.monotonic() - start
                return prov, result, elapsed
            except Exception as e:
                elapsed = time.monotonic() - start
                return prov, f"Ошибка: {e}", elapsed

        results = await asyncio.gather(*[_critique(p) for p in providers])
        return {prov: (critique, elapsed) for prov, critique, elapsed in results}

    async def summarize(
        self,
        question: str,
        answers: dict[str, tuple[str, float]],
        critiques: dict[str, tuple[str, float]],
    ) -> str:
        """Generate final summary from one of the models."""
        # Build all content text
        parts = []
        for prov in answers:
            display = self.ai_router.get_display_name(prov)
            answer_text = answers[prov][0]
            parts.append(f"Ответ {display}:\n{answer_text}")
            if prov in critiques:
                critique_text = critiques[prov][0]
                parts.append(f"Анализ {display}:\n{critique_text}")

        all_content = "\n\n".join(parts)
        prompt = SUMMARY_PROMPT.format(question=question, all_content=all_content)

        # Use default provider for summary
        svc = self.ai_router.get_service()
        messages = [{"role": "user", "content": prompt}]
        try:
            return await svc.generate(messages)
        except Exception as e:
            return f"Ошибка при подведении итогов: {e}"

    def format_round1(self, answers: dict[str, tuple[str, float]]) -> str:
        """Format initial answers for display."""
        parts = []
        timings = []
        for prov, (answer, elapsed) in answers.items():
            display = self.ai_router.get_display_name(prov)
            parts.append(f"{display}:\n{answer}")
            name_short = display.split(" ", 1)[-1] if " " in display else display
            timings.append(f"{name_short} {elapsed:.1f}с")

        text = "\u2501\u2501\u2501 Раунд 1: Ответы \u2501\u2501\u2501\n\n"
        text += "\n\n\u2501\u2501\u2501\n\n".join(parts)
        text += f"\n\n{' | '.join(timings)}"
        return text

    def format_debate(self, critiques: dict[str, tuple[str, float]]) -> str:
        """Format debate round for display."""
        parts = []
        timings = []
        for prov, (critique, elapsed) in critiques.items():
            display = self.ai_router.get_display_name(prov)
            parts.append(f"{display} анализирует:\n{critique}")
            name_short = display.split(" ", 1)[-1] if " " in display else display
            timings.append(f"{name_short} {elapsed:.1f}с")

        text = "\u2501\u2501\u2501 Раунд 2: Дебаты \u2501\u2501\u2501\n\n"
        text += "\n\n\u2501\u2501\u2501\n\n".join(parts)
        text += f"\n\n{' | '.join(timings)}"
        return text
