"""Settings menu handler."""

import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile

from bot.keyboards.settings import build_settings_keyboard, VOICE_LABELS, STYLE_LABELS, IMAGE_LABELS
from bot.services.settings_service import SettingsService
from bot.services.ai_router import AIRouter
from bot.services.voice_service import VoiceService
from bot.services.balance_service import BalanceService

logger = logging.getLogger(__name__)
router = Router()

SETTINGS_HEADER = "<b>Настройки</b>"


async def _refresh_keyboard(callback: CallbackQuery, settings_service: SettingsService):
    s = await settings_service.get(callback.from_user.id)
    kb = build_settings_keyboard(
        current_model=s.selected_model,
        current_voice=s.tts_voice,
        current_style=s.response_style,
        auto_search=s.auto_search,
        auto_memory=s.auto_memory,
        current_image_provider=s.image_provider,
    )
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass


# ── Entry point ──

@router.message(F.text == "Настройки")
async def btn_settings(message: Message, settings_service: SettingsService):
    s = await settings_service.get(message.from_user.id)
    kb = build_settings_keyboard(
        current_model=s.selected_model,
        current_voice=s.tts_voice,
        current_style=s.response_style,
        auto_search=s.auto_search,
        auto_memory=s.auto_memory,
        current_image_provider=s.image_provider,
    )
    await message.answer(SETTINGS_HEADER, parse_mode="HTML", reply_markup=kb)


# ── Noop (section headers) ──

@router.callback_query(F.data == "set:noop")
async def on_noop(callback: CallbackQuery):
    await callback.answer()


# ── Model ──

@router.callback_query(F.data.startswith("set:model:"))
async def on_set_model(
    callback: CallbackQuery,
    settings_service: SettingsService,
    ai_router: AIRouter,
):
    provider = callback.data.split(":")[2]
    user_id = callback.from_user.id

    if provider not in ai_router.services:
        await callback.answer("Модель недоступна", show_alert=True)
        return

    await settings_service.update(user_id, selected_model=provider)
    await ai_router.save_user_provider(user_id, provider)

    display = ai_router.get_display_name(provider)
    await callback.answer(f"Модель: {display}")
    await _refresh_keyboard(callback, settings_service)


# ── TTS voice ──

@router.callback_query(F.data.startswith("set:voice:"))
async def on_set_voice(callback: CallbackQuery, settings_service: SettingsService):
    voice = callback.data.split(":")[2]
    user_id = callback.from_user.id

    if voice not in VOICE_LABELS:
        await callback.answer("Неизвестный голос", show_alert=True)
        return

    await settings_service.update(user_id, tts_voice=voice)
    await callback.answer(f"Голос: {VOICE_LABELS[voice]}")
    await _refresh_keyboard(callback, settings_service)


@router.callback_query(F.data == "set:voice_test")
async def on_voice_test(
    callback: CallbackQuery,
    settings_service: SettingsService,
    voice_service: VoiceService,
    balance_service: BalanceService,
):
    user_id = callback.from_user.id
    s = await settings_service.get(user_id)
    voice = s.tts_voice
    label = VOICE_LABELS.get(voice, voice)

    await callback.answer(f"Тест: {label}...")

    test_text = "Это тестовое сообщение для проверки голоса."
    try:
        audio_bytes, char_count = await voice_service.synthesize(test_text, voice=voice)
        voice_file = BufferedInputFile(audio_bytes, filename="voice_test.mp3")
        await callback.message.answer_voice(voice_file)
        if balance_service:
            await balance_service.track_tts(char_count)
    except Exception as e:
        logger.exception("Voice test failed")
        await callback.message.answer(f"Ошибка теста: {str(e)[:200]}")


# ── Response style ──

@router.callback_query(F.data.startswith("set:style:"))
async def on_set_style(callback: CallbackQuery, settings_service: SettingsService):
    style = callback.data.split(":")[2]
    user_id = callback.from_user.id

    if style not in STYLE_LABELS:
        await callback.answer("Неизвестный стиль", show_alert=True)
        return

    await settings_service.update(user_id, response_style=style)
    await callback.answer(f"Стиль: {STYLE_LABELS[style]}")
    await _refresh_keyboard(callback, settings_service)


# ── Auto-search ──

@router.callback_query(F.data.startswith("set:search:"))
async def on_set_search(callback: CallbackQuery, settings_service: SettingsService):
    val = callback.data.split(":")[2]
    enabled = val == "on"
    await settings_service.update(callback.from_user.id, auto_search=enabled)
    await callback.answer(f"Автопоиск: {'Вкл' if enabled else 'Выкл'}")
    await _refresh_keyboard(callback, settings_service)


# ── Auto-memory ──

@router.callback_query(F.data.startswith("set:memory:"))
async def on_set_memory(callback: CallbackQuery, settings_service: SettingsService):
    val = callback.data.split(":")[2]
    enabled = val == "on"
    await settings_service.update(callback.from_user.id, auto_memory=enabled)
    await callback.answer(f"Автопамять: {'Вкл' if enabled else 'Выкл'}")
    await _refresh_keyboard(callback, settings_service)


# ── Image provider ──

@router.callback_query(F.data.startswith("set:imgprov:"))
async def on_set_image_provider(callback: CallbackQuery, settings_service: SettingsService):
    provider = callback.data.split(":")[2]
    user_id = callback.from_user.id

    if provider not in IMAGE_LABELS:
        await callback.answer("Неизвестный провайдер", show_alert=True)
        return

    await settings_service.update(user_id, image_provider=provider)
    await callback.answer(f"Изображения: {IMAGE_LABELS[provider]}")
    await _refresh_keyboard(callback, settings_service)


# ── Back ──

@router.callback_query(F.data == "set:back")
async def on_back(callback: CallbackQuery):
    await callback.answer()
    await callback.message.delete()
