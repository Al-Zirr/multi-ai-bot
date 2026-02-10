"""Publish long AI responses to Telegraph (telegra.ph)."""

import logging
from telegraph.aio import Telegraph

from bot.utils.formatting import md_to_html

logger = logging.getLogger(__name__)


class TelegraphService:
    def __init__(self):
        self.telegraph = Telegraph()
        self._initialized = False

    async def _ensure_account(self):
        if not self._initialized:
            await self.telegraph.create_account(
                short_name="MultiAIBot",
                author_name="Multi-AI Bot",
            )
            self._initialized = True

    async def publish(self, title: str, content: str, author: str = "") -> str | None:
        """Publish content to Telegraph. Returns URL or None on failure."""
        try:
            await self._ensure_account()

            html_content = md_to_html(content)

            response = await self.telegraph.create_page(
                title=title[:256],
                html_content=html_content,
                author_name=author or "Multi-AI Bot",
            )
            url = response.get("url", "")
            logger.info("Published to Telegraph: %s (%d chars)", url, len(content))
            return url
        except Exception:
            logger.exception("Failed to publish to Telegraph")
            return None
