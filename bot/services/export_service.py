"""Export conversations to Markdown, JSON, PDF."""

import json
import logging
from datetime import datetime

from sqlalchemy import select

from bot.database import async_session
from bot.models.conversation import Conversation

logger = logging.getLogger(__name__)

MODEL_LABELS = {
    "gpt": "GPT",
    "claude": "Claude",
    "gemini": "Gemini",
}


class ExportService:

    async def _load_messages(self, user_id: int) -> list[Conversation]:
        async with async_session() as session:
            rows = await session.execute(
                select(Conversation)
                .where(Conversation.user_id == user_id)
                .order_by(Conversation.id.asc())
            )
            return list(rows.scalars().all())

    async def export_markdown(self, user_id: int) -> tuple[bytes, str]:
        messages = await self._load_messages(user_id)
        now = datetime.now()
        lines = [f"# Диалог — {now.strftime('%d.%m.%Y')}", ""]

        for msg in messages:
            if msg.role == "system":
                continue
            if msg.role == "user":
                lines.append("## User")
            else:
                model_label = MODEL_LABELS.get(msg.model, msg.model or "AI")
                lines.append(f"## Assistant ({model_label})")
            lines.append(msg.content)
            lines.append("")
            lines.append("---")
            lines.append("")

        text = "\n".join(lines)
        filename = f"dialog_{now.strftime('%Y%m%d_%H%M%S')}.md"
        return text.encode("utf-8"), filename

    async def export_json(self, user_id: int) -> tuple[bytes, str]:
        messages = await self._load_messages(user_id)
        now = datetime.now()

        data = {
            "exported_at": now.isoformat(),
            "user_id": user_id,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat() if msg.created_at else None,
                    "model": msg.model,
                }
                for msg in messages
                if msg.role != "system"
            ],
        }

        text = json.dumps(data, ensure_ascii=False, indent=2)
        filename = f"dialog_{now.strftime('%Y%m%d_%H%M%S')}.json"
        return text.encode("utf-8"), filename

    async def export_pdf(self, user_id: int) -> tuple[bytes, str]:
        messages = await self._load_messages(user_id)
        now = datetime.now()

        # Build HTML for PyMuPDF Story
        html_parts = [
            "<h1>Диалог</h1>",
            f"<p><i>Экспортировано: {now.strftime('%d.%m.%Y %H:%M')}</i></p>",
            "<hr>",
        ]

        for msg in messages:
            if msg.role == "system":
                continue
            if msg.role == "user":
                html_parts.append("<h3>User</h3>")
            else:
                model_label = MODEL_LABELS.get(msg.model, msg.model or "AI")
                html_parts.append(f"<h3>Assistant ({model_label})</h3>")
            # Escape HTML in content and preserve newlines
            content = (
                msg.content
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>")
            )
            html_parts.append(f"<p>{content}</p>")
            html_parts.append("<hr>")

        html = "\n".join(html_parts)

        import fitz  # PyMuPDF

        story = fitz.Story(html)

        page_rect = fitz.paper_rect("a4")
        content_rect = page_rect + (36, 36, -36, -36)  # 0.5 inch margins

        def rectfn(rect_num, filled):
            return content_rect, page_rect, fitz.Matrix()

        doc = story.write_with_links(rectfn)
        pdf_bytes = doc.tobytes()
        doc.close()

        filename = f"dialog_{now.strftime('%Y%m%d_%H%M%S')}.pdf"
        return pdf_bytes, filename
