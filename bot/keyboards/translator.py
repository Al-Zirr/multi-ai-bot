from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_translator_menu(
    prompt_names: list[str] | None = None,
    active_prompt: str | None = None,
) -> ReplyKeyboardMarkup:
    keyboard = [
        [
            KeyboardButton(text="Рус \u2192 Араб"),
            KeyboardButton(text="Араб \u2192 Рус"),
            KeyboardButton(text="Авто"),
        ],
        [
            KeyboardButton(text="Сравнить 3 модели"),
            KeyboardButton(text="Глоссарий"),
        ],
    ]

    if prompt_names:
        prompt_buttons = []
        for name in prompt_names:
            if name == active_prompt:
                prompt_buttons.append(KeyboardButton(text=f"\u2713 {name}"))
            else:
                prompt_buttons.append(KeyboardButton(text=f"\u00b7 {name}"))
        if active_prompt:
            prompt_buttons.append(KeyboardButton(text="\u00b7 \u0421\u0442\u0430\u043d\u0434\u0430\u0440\u0442"))
        else:
            prompt_buttons.append(KeyboardButton(text="\u2713 \u0421\u0442\u0430\u043d\u0434\u0430\u0440\u0442"))
        for i in range(0, len(prompt_buttons), 3):
            keyboard.append(prompt_buttons[i:i + 3])

    keyboard.append([KeyboardButton(text="Вернуться в чат")])

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
