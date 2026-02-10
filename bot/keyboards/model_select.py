from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

LABELS = {
    "gpt": "GPT",
    "claude": "Claude",
    "gemini": "Gemini",
}


def get_model_keyboard(
    available: list[str],
    current: str,
    model_versions: dict[str, str] | None = None,
) -> InlineKeyboardMarkup:
    """model_versions: {"gpt": "gpt-5.2", "claude": "claude-opus-4-6", ...}"""
    buttons = []
    for provider in available:
        label = LABELS.get(provider, provider)
        marker = " \u2713" if provider == current else ""
        buttons.append(
            InlineKeyboardButton(
                text=f"{label}{marker}",
                callback_data=f"model:{provider}",
            )
        )
    buttons.append(
        InlineKeyboardButton(
            text="Все" if current != "all" else "Все \u2713",
            callback_data="model:all",
        )
    )
    close_row = [InlineKeyboardButton(text="\u2190 Закрыть", callback_data="model:close")]
    return InlineKeyboardMarkup(inline_keyboard=[buttons, close_row])


def get_response_keyboard(
    current_provider: str,
    model_versions: dict[str, str] | None = None,
) -> InlineKeyboardMarkup:
    """Inline buttons under each AI response."""
    versions = model_versions or {}

    row1 = [
        InlineKeyboardButton(
            text="Перегенерировать",
            callback_data="regen",
        ),
    ]

    row2 = []
    for provider in ["gpt", "claude", "gemini"]:
        if provider == current_provider:
            continue
        label = LABELS.get(provider, provider)
        version = versions.get(provider, provider)
        row2.append(
            InlineKeyboardButton(
                text=f"{label}: {version}",
                callback_data=f"ask:{provider}",
            )
        )

    row3 = [
        InlineKeyboardButton(
            text="Озвучить",
            callback_data="tts",
        ),
        InlineKeyboardButton(
            text="Сохранить",
            callback_data="bookmark",
        ),
    ]

    return InlineKeyboardMarkup(inline_keyboard=[row1, row2, row3])
