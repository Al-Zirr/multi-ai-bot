from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

MODEL_LABELS = {"gpt": "GPT", "claude": "Claude", "gemini": "Gemini"}

VOICE_LABELS = {
    "ash": "Мягкий",
    "onyx": "Глубокий",
    "echo": "Звонкий",
    "alloy": "Нейтральный",
    "nova": "Энергичный",
    "shimmer": "Лёгкий",
}

STYLE_LABELS = {"short": "Коротко", "medium": "Средне", "detailed": "Подробно"}

IMAGE_LABELS = {"dalle": "GPT Image", "imagen": "Gemini Image", "flux": "Flux 2 Pro"}


def _mark(label: str, is_current: bool) -> str:
    return f"{label} \u2713" if is_current else label


def build_settings_keyboard(
    current_model: str,
    current_voice: str,
    current_style: str,
    auto_search: bool,
    auto_memory: bool,
    current_image_provider: str,
) -> InlineKeyboardMarkup:
    rows = []

    # Model
    rows.append([InlineKeyboardButton(text="Модель по умолчанию", callback_data="set:noop")])
    rows.append([
        InlineKeyboardButton(text=_mark(label, key == current_model), callback_data=f"set:model:{key}")
        for key, label in MODEL_LABELS.items()
    ])

    # TTS voice — 2 rows of 3
    rows.append([InlineKeyboardButton(text="Голос TTS", callback_data="set:noop")])
    voice_keys = list(VOICE_LABELS.keys())
    rows.append([
        InlineKeyboardButton(text=_mark(VOICE_LABELS[k], k == current_voice), callback_data=f"set:voice:{k}")
        for k in voice_keys[:3]
    ])
    rows.append([
        InlineKeyboardButton(text=_mark(VOICE_LABELS[k], k == current_voice), callback_data=f"set:voice:{k}")
        for k in voice_keys[3:]
    ])
    rows.append([InlineKeyboardButton(text="Тест", callback_data="set:voice_test")])

    # Response style
    rows.append([InlineKeyboardButton(text="Стиль ответов", callback_data="set:noop")])
    rows.append([
        InlineKeyboardButton(text=_mark(label, key == current_style), callback_data=f"set:style:{key}")
        for key, label in STYLE_LABELS.items()
    ])

    # Auto-search toggle
    rows.append([
        InlineKeyboardButton(
            text=f"Автопоиск: {'Вкл \u2713' if auto_search else 'Выкл'}",
            callback_data=f"set:search:{'off' if auto_search else 'on'}",
        )
    ])

    # Auto-memory toggle
    rows.append([
        InlineKeyboardButton(
            text=f"Автопамять: {'Вкл \u2713' if auto_memory else 'Выкл'}",
            callback_data=f"set:memory:{'off' if auto_memory else 'on'}",
        )
    ])

    # Image provider
    rows.append([InlineKeyboardButton(text="Провайдер изображений", callback_data="set:noop")])
    rows.append([
        InlineKeyboardButton(text=_mark(label, key == current_image_provider), callback_data=f"set:imgprov:{key}")
        for key, label in IMAGE_LABELS.items()
    ])

    # Back
    rows.append([InlineKeyboardButton(text="\u2190 Назад", callback_data="set:back")])

    return InlineKeyboardMarkup(inline_keyboard=rows)
