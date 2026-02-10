"""Track spending across all paid services."""

import logging
from sqlalchemy import select
from bot.database import async_session
from bot.models.service_balance import ServiceBalance

logger = logging.getLogger(__name__)

# Pricing per 1M tokens
PRICING = {
    "gpt": {"input": 1.75, "output": 14.00},       # GPT-5.2
    "claude": {"input": 15.00, "output": 75.00},    # Claude Opus 4.6
    "gemini": {"input": 1.25, "output": 10.00},     # Gemini 3 Pro
}

# Provider → service name mapping
PROVIDER_SERVICE = {
    "gpt": "openai",
    "claude": "anthropic",
    "gemini": "gemini",
}

WHISPER_PRICE_PER_MINUTE = 0.006


class BalanceService:

    async def track_ai_usage(self, provider: str, input_tokens: int, output_tokens: int):
        """Track AI model token usage and update balance."""
        pricing = PRICING.get(provider)
        if not pricing:
            return

        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
        service_name = PROVIDER_SERVICE.get(provider, provider)

        await self._subtract(service_name, cost)
        logger.info(
            "Balance: %s used %d in + %d out tokens = $%.4f",
            provider, input_tokens, output_tokens, cost,
        )

    async def track_whisper(self, duration_seconds: float):
        """Track Whisper STT usage (billed per minute)."""
        cost = (duration_seconds / 60.0) * WHISPER_PRICE_PER_MINUTE
        await self._subtract("openai", cost)
        logger.info("Balance: Whisper %.1fs = $%.4f", duration_seconds, cost)

    async def track_tts(self, char_count: int):
        """Track OpenAI TTS usage (billed per character, $12/1M for gpt-4o-mini-tts)."""
        cost = (char_count / 1_000_000) * 12.0
        await self._subtract("openai", cost)
        logger.info("Balance: OpenAI TTS %d chars = $%.4f", char_count, cost)

    async def track_tavily(self):
        """Track Tavily search usage (1 request)."""
        await self._subtract("tavily", 1)
        logger.info("Balance: Tavily -1 request")

    async def get_balance(self, service: str) -> dict | None:
        """Get balance for a service."""
        try:
            async with async_session() as session:
                stmt = select(ServiceBalance).where(ServiceBalance.service == service)
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()
                if row:
                    return {
                        "service": row.service,
                        "balance": row.balance,
                        "spent": row.spent,
                        "unit": row.unit,
                        "warn": row.balance <= row.warn_threshold,
                    }
        except Exception:
            logger.exception("Failed to get balance for %s", service)
        return None

    async def get_all_balances(self) -> list[dict]:
        """Get balances for all services."""
        try:
            async with async_session() as session:
                stmt = select(ServiceBalance).order_by(ServiceBalance.id)
                result = await session.execute(stmt)
                rows = result.scalars().all()
                return [
                    {
                        "service": r.service,
                        "balance": r.balance,
                        "spent": r.spent,
                        "unit": r.unit,
                        "warn": r.balance <= r.warn_threshold,
                    }
                    for r in rows
                ]
        except Exception:
            logger.exception("Failed to get all balances")
            return []

    async def format_balance_for_signature(self, provider: str) -> str:
        """Format balance string for response signature."""
        service_name = PROVIDER_SERVICE.get(provider, provider)
        info = await self.get_balance(service_name)
        if not info:
            return ""
        if info["unit"] == "$":
            text = f"${info['balance']:.2f}"
        else:
            text = f"{int(info['balance'])} {info['unit']}"
        if info["warn"]:
            text += " (!)"
        return text

    async def set_balance(self, service: str, new_balance: float):
        """Manually set balance for a service."""
        try:
            async with async_session() as session:
                stmt = select(ServiceBalance).where(ServiceBalance.service == service)
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()
                if row:
                    row.balance = new_balance
                    await session.commit()
                    logger.info("Balance manually set: %s = %.2f", service, new_balance)
        except Exception:
            logger.exception("Failed to set balance for %s", service)

    async def track_image_generation(self, service: str, cost: float):
        """Track image generation cost (DALL-E / Imagen)."""
        await self._subtract(service, cost)
        logger.info("Balance: Image gen %s = $%.4f", service, cost)

    async def _subtract(self, service: str, amount: float):
        """Subtract amount from service balance, add to spent."""
        try:
            async with async_session() as session:
                stmt = select(ServiceBalance).where(ServiceBalance.service == service)
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()
                if row:
                    row.balance = max(0, row.balance - amount)
                    row.spent += amount
                    await session.commit()
        except Exception:
            logger.exception("Failed to update balance for %s", service)
