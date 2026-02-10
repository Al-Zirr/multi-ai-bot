from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Модель"),
                KeyboardButton(text="Контекст"),
                KeyboardButton(text="Очистить"),
            ],
            [
                KeyboardButton(text="Переводчик"),
                KeyboardButton(text="Поиск"),
                KeyboardButton(text="Генерация"),
            ],
            [
                KeyboardButton(text="Память"),
                KeyboardButton(text="Баланс"),
                KeyboardButton(text="Настройки"),
            ],
        ],
        resize_keyboard=True,
    )
