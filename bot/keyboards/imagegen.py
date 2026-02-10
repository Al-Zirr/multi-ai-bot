from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


PROVIDER_LABELS = {
    "dalle": "DALL-E 3",
    "imagen": "Gemini Imagen",
    "flux": "Flux 2 Pro",
}

SIZE_LABELS = {
    "1024x1024": "1:1",
    "1792x1024": "16:9",
    "1024x1792": "9:16",
}


def get_image_result_keyboard(
    current_provider: str,
    current_size: str,
    current_style: str,
    current_quality: str,
    available_providers: list[str],
) -> InlineKeyboardMarkup:
    rows = []

    # Row 1: Regenerate
    rows.append([InlineKeyboardButton(text="Ещё раз", callback_data="img:regen")])

    # Row 2: Size (DALL-E only)
    if current_provider == "dalle":
        size_buttons = []
        for size, label in SIZE_LABELS.items():
            text = f"\u2713 {label}" if size == current_size else label
            size_buttons.append(
                InlineKeyboardButton(text=text, callback_data=f"img:size:{size}")
            )
        rows.append(size_buttons)

    # Row 3: Style + Quality (DALL-E only)
    if current_provider == "dalle":
        style_buttons = []
        for style, label in [("vivid", "Vivid"), ("natural", "Natural")]:
            text = f"\u2713 {label}" if style == current_style else label
            style_buttons.append(
                InlineKeyboardButton(text=text, callback_data=f"img:style:{style}")
            )
        # Quality toggle
        q_text = "\u2713 HD" if current_quality == "hd" else "HD"
        q_new = "standard" if current_quality == "hd" else "hd"
        style_buttons.append(
            InlineKeyboardButton(text=q_text, callback_data=f"img:quality:{q_new}")
        )
        rows.append(style_buttons)

    # Row 4: Provider switch
    if len(available_providers) > 1:
        other = [p for p in available_providers if p != current_provider]
        for prov in other:
            label = PROVIDER_LABELS.get(prov, prov)
            rows.append([
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"img:provider:{prov}",
                )
            ])

    rows.append([InlineKeyboardButton(text="\u2190 Закрыть", callback_data="img:close")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
