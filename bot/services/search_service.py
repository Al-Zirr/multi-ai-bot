import logging
import re

from tavily import AsyncTavilyClient

logger = logging.getLogger(__name__)

# Keywords that suggest a search is needed
SEARCH_TRIGGERS_RU = {
    "сейчас", "сегодня", "вчера", "последние новости", "новости",
    "текущий курс", "курс доллара", "курс евро", "погода",
    "актуальн", "свежи", "недавно", "на данный момент",
    "в 2025", "в 2026", "в этом году", "последн",
    "сколько стоит", "какой курс", "цена", "стоимость",
    "биткоин", "bitcoin", "crypto", "крипто",
    "результат матча", "счёт", "выборы", "рейтинг",
}

SEARCH_TRIGGERS_EN = {
    "latest", "today", "yesterday", "current", "news",
    "right now", "recently", "up to date", "this year",
}


class SearchService:
    def __init__(self, api_key: str, auto_search: bool = True):
        self.client = AsyncTavilyClient(api_key=api_key)
        self.auto_search = auto_search

    def should_search(self, text: str) -> bool:
        """Check if text contains keywords suggesting a web search is needed."""
        if not self.auto_search:
            return False
        lower = text.lower()
        for trigger in SEARCH_TRIGGERS_RU | SEARCH_TRIGGERS_EN:
            if trigger in lower:
                return True
        # URL detection
        if re.search(r"https?://", text):
            return True
        return False

    async def search(self, query: str, max_results: int = 5) -> str:
        """Search the web and return formatted results."""
        try:
            results = await self.client.search(
                query=query,
                max_results=max_results,
                search_depth="basic",
            )
        except Exception as e:
            logger.exception("Tavily search failed")
            return f"Ошибка поиска: {e}"

        if not results.get("results"):
            return "Ничего не найдено."

        formatted = []
        for r in results["results"]:
            title = r.get("title", "")
            url = r.get("url", "")
            content = r.get("content", "")
            formatted.append(f"\u2022 {title}\n  {url}\n  {content}")

        return "\n\n".join(formatted)

    async def search_for_ai(self, query: str, max_results: int = 5) -> str:
        """Search and format results as context for AI."""
        try:
            results = await self.client.search(
                query=query,
                max_results=max_results,
                search_depth="basic",
            )
        except Exception as e:
            logger.exception("Tavily search failed")
            return ""

        if not results.get("results"):
            return ""

        parts = []
        for r in results["results"]:
            title = r.get("title", "")
            url = r.get("url", "")
            content = r.get("content", "")
            parts.append(f"[{title}]({url})\n{content}")

        return "\n\n---\n\n".join(parts)
