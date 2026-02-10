"""Convert AI Markdown output to Telegram-compatible HTML."""

import html
import re

# Box-drawing characters used in Unicode tables
_BOX_CHARS = set("┌┐└┘├┤┬┴┼─│═║╔╗╚╝╠╣╦╩╬")


def md_to_html(text: str) -> str:
    """Convert Markdown to Telegram HTML.

    Handles: code blocks, inline code, bold, italic,
    strikethrough, headers, links, Unicode tables.
    Falls back to escaped plain text on any error.
    """
    try:
        return _convert(text)
    except Exception:
        return html.escape(text)


def _is_table_line(line: str) -> bool:
    """Check if a line is part of a Unicode box-drawing table."""
    stripped = line.strip()
    if not stripped:
        return False
    return any(ch in _BOX_CHARS for ch in stripped)


def _wrap_tables(text: str) -> str:
    """Find consecutive lines with box-drawing chars and wrap in <pre>."""
    lines = text.split("\n")
    result = []
    table_buf: list[str] = []

    def flush_table():
        if table_buf:
            table_text = html.escape("\n".join(table_buf))
            result.append(f"<pre>{table_text}</pre>")
            table_buf.clear()

    for line in lines:
        if _is_table_line(line):
            table_buf.append(line)
        else:
            flush_table()
            result.append(line)

    flush_table()
    return "\n".join(result)


def _convert(text: str) -> str:
    placeholders: list[str] = []

    def _store(replacement: str) -> str:
        idx = len(placeholders)
        placeholders.append(replacement)
        return f"\x00PH{idx}\x00"

    # 1) Fenced code blocks: ```lang\ncode\n```
    def _code_block(m: re.Match) -> str:
        lang = m.group(1) or ""
        code = html.escape(m.group(2).strip("\n"))
        if lang:
            return _store(f"<pre><code class=\"language-{lang}\">{code}</code></pre>")
        return _store(f"<pre>{code}</pre>")

    text = re.sub(r"```(\w*)\n?(.*?)```", _code_block, text, flags=re.DOTALL)

    # 2) Unicode box-drawing tables → <pre> blocks
    def _table_block(m: re.Match) -> str:
        table_text = html.escape(m.group(0))
        return _store(f"<pre>{table_text}</pre>")

    # Match consecutive lines containing box-drawing characters
    text = re.sub(
        r"(?:^.*[┌┐└┘├┤┬┴┼─│═║╔╗╚╝╠╣╦╩╬].*$\n?)+",
        _table_block,
        text,
        flags=re.MULTILINE,
    )

    # 3) Inline code: `code`
    def _inline_code(m: re.Match) -> str:
        return _store(f"<code>{html.escape(m.group(1))}</code>")

    text = re.sub(r"`([^`\n]+)`", _inline_code, text)

    # 4) Escape HTML in the rest
    text = html.escape(text)

    # 5) Headers: # text → bold line
    text = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)

    # 6) Bold + italic: ***text*** or ___text___
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", text)

    # 7) Bold: **text** or __text__
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)

    # 8) Italic: *text* or _text_ (word-boundary aware for _)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<i>\1</i>", text)

    # 9) Strikethrough: ~~text~~
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)

    # 10) Links: [text](url) — html.escape does NOT touch [ ] ( )
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r'<a href="\2">\1</a>',
        text,
    )

    # 11) Restore placeholders
    for idx, replacement in enumerate(placeholders):
        text = text.replace(f"\x00PH{idx}\x00", replacement)

    return text
