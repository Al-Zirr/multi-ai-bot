from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_youtube_menu(video_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Выжимка", callback_data=f"yt:sum:{video_id}"),
            InlineKeyboardButton(text="Скачать видео", callback_data=f"yt:vid:{video_id}"),
            InlineKeyboardButton(text="Скачать аудио", callback_data=f"yt:aud:{video_id}"),
        ],
    ])


def get_video_quality_keyboard(video_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="360p", callback_data=f"yt:vq:{video_id}:360"),
            InlineKeyboardButton(text="480p", callback_data=f"yt:vq:{video_id}:480"),
            InlineKeyboardButton(text="720p", callback_data=f"yt:vq:{video_id}:720"),
        ],
        [
            InlineKeyboardButton(text="1080p", callback_data=f"yt:vq:{video_id}:1080"),
            InlineKeyboardButton(text="Лучшее", callback_data=f"yt:vq:{video_id}:best"),
        ],
        [
            InlineKeyboardButton(text="\u2190 Назад", callback_data=f"yt:back:{video_id}"),
        ],
    ])


def get_audio_format_keyboard(video_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="MP3 128kbps", callback_data=f"yt:af:{video_id}:mp3_128"),
            InlineKeyboardButton(text="MP3 320kbps", callback_data=f"yt:af:{video_id}:mp3_320"),
        ],
        [
            InlineKeyboardButton(text="WAV", callback_data=f"yt:af:{video_id}:wav"),
        ],
        [
            InlineKeyboardButton(text="\u2190 Назад", callback_data=f"yt:back:{video_id}"),
        ],
    ])


def get_summary_keyboard(video_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Задать вопрос по видео", callback_data=f"yt:ask:{video_id}"),
        ],
        [
            InlineKeyboardButton(text="Скачать видео", callback_data=f"yt:vid:{video_id}"),
            InlineKeyboardButton(text="Скачать аудио", callback_data=f"yt:aud:{video_id}"),
        ],
        [
            InlineKeyboardButton(text="\u2190 Назад", callback_data=f"yt:back:{video_id}"),
        ],
    ])
