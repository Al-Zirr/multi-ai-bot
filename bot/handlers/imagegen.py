"""Image generation handler: DALL-E 3 + Gemini Imagen."""

import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile

from bot.keyboards.imagegen import get_image_result_keyboard, PROVIDER_LABELS
from bot.services.balance_service import BalanceService
from bot.services.image_service import ImageService, ImageGenParams
from bot.services.quota_service import QuotaService
from bot.services.settings_service import SettingsService

logger = logging.getLogger(__name__)
router = Router()

# Per-user last generation params
_user_image_params: dict[int, ImageGenParams] = {}


# ═══════════════════════════════════════════════════════
#  COMMAND: /imagine
# ═══════════════════════════════════════════════════════

@router.message(Command("imagine"))
async def cmd_imagine(
    message: Message,
    image_service: ImageService,
    balance_service: BalanceService,
    settings_service: SettingsService,
    quota_service: QuotaService,
):
    prompt = message.text.removeprefix("/imagine").strip()
    if not prompt:
        await message.answer(
            "<b>Генерация изображений</b>\n\n"
            "Использование: <code>/imagine описание картинки</code>\n\n"
            "Примеры:\n"
            "\u2022 <code>/imagine кот в космосе</code>\n"
            "\u2022 <code>/imagine минималистичный логотип</code>",
            parse_mode="HTML",
        )
        return

    user_id = message.from_user.id

    # Check image quota
    allowed, error_msg = await quota_service.check_images(user_id)
    if not allowed:
        await message.answer(error_msg, parse_mode="HTML")
        return

    prev = _user_image_params.get(user_id)

    # Default provider from user settings if no previous params
    if prev:
        default_provider = prev.provider
    else:
        s = await settings_service.get(user_id)
        default_provider = s.image_provider

    params = ImageGenParams(
        prompt=prompt,
        provider=default_provider,
        size=prev.size if prev else "1024x1024",
        style=prev.style if prev else "vivid",
        quality=prev.quality if prev else "standard",
    )
    _user_image_params[user_id] = params

    await _generate_and_send(message, params, image_service, balance_service, quota_service, user_id)


# ═══════════════════════════════════════════════════════
#  MENU BUTTON
# ═══════════════════════════════════════════════════════

@router.message(F.text == "Генерация")
async def btn_imagine(message: Message):
    await message.answer(
        "<b>Генерация изображений</b>\n\n"
        "Отправьте команду:\n"
        "<code>/imagine описание картинки</code>\n\n"
        "Провайдеры: DALL-E 3, Gemini Imagen 3",
        parse_mode="HTML",
    )


# ═══════════════════════════════════════════════════════
#  CALLBACKS
# ═══════════════════════════════════════════════════════

@router.callback_query(F.data == "img:close")
async def on_close(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data == "img:regen")
async def on_regen(
    callback: CallbackQuery,
    image_service: ImageService,
    balance_service: BalanceService,
    quota_service: QuotaService,
):
    user_id = callback.from_user.id
    params = _user_image_params.get(user_id)
    if not params:
        await callback.answer("Нет промпта для повторной генерации", show_alert=True)
        return

    allowed, _ = await quota_service.check_images(user_id)
    if not allowed:
        await callback.answer("Лимит изображений исчерпан", show_alert=True)
        return

    await callback.answer("Генерирую заново...")
    await _generate_and_send(callback.message, params, image_service, balance_service, quota_service, user_id)


@router.callback_query(F.data.startswith("img:size:"))
async def on_change_size(
    callback: CallbackQuery,
    image_service: ImageService,
    balance_service: BalanceService,
    quota_service: QuotaService,
):
    user_id = callback.from_user.id
    params = _user_image_params.get(user_id)
    if not params:
        await callback.answer("Сначала сгенерируйте изображение", show_alert=True)
        return
    allowed, _ = await quota_service.check_images(user_id)
    if not allowed:
        await callback.answer("Лимит изображений исчерпан", show_alert=True)
        return
    params.size = callback.data.split(":")[2]
    await callback.answer(f"Размер: {params.size}")
    await _generate_and_send(callback.message, params, image_service, balance_service, quota_service, user_id)


@router.callback_query(F.data.startswith("img:style:"))
async def on_change_style(
    callback: CallbackQuery,
    image_service: ImageService,
    balance_service: BalanceService,
    quota_service: QuotaService,
):
    user_id = callback.from_user.id
    params = _user_image_params.get(user_id)
    if not params:
        await callback.answer("Сначала сгенерируйте изображение", show_alert=True)
        return
    allowed, _ = await quota_service.check_images(user_id)
    if not allowed:
        await callback.answer("Лимит изображений исчерпан", show_alert=True)
        return
    params.style = callback.data.split(":")[2]
    await callback.answer(f"Стиль: {params.style}")
    await _generate_and_send(callback.message, params, image_service, balance_service, quota_service, user_id)


@router.callback_query(F.data.startswith("img:quality:"))
async def on_change_quality(
    callback: CallbackQuery,
    image_service: ImageService,
    balance_service: BalanceService,
    quota_service: QuotaService,
):
    user_id = callback.from_user.id
    params = _user_image_params.get(user_id)
    if not params:
        await callback.answer("Сначала сгенерируйте изображение", show_alert=True)
        return
    allowed, _ = await quota_service.check_images(user_id)
    if not allowed:
        await callback.answer("Лимит изображений исчерпан", show_alert=True)
        return
    params.quality = callback.data.split(":")[2]
    await callback.answer(f"{'HD' if params.quality == 'hd' else 'Standard'}")
    await _generate_and_send(callback.message, params, image_service, balance_service, quota_service, user_id)


@router.callback_query(F.data.startswith("img:provider:"))
async def on_change_provider(
    callback: CallbackQuery,
    image_service: ImageService,
    balance_service: BalanceService,
    quota_service: QuotaService,
):
    user_id = callback.from_user.id
    params = _user_image_params.get(user_id)
    if not params:
        await callback.answer("Сначала сгенерируйте изображение", show_alert=True)
        return
    allowed, _ = await quota_service.check_images(user_id)
    if not allowed:
        await callback.answer("Лимит изображений исчерпан", show_alert=True)
        return
    params.provider = callback.data.split(":")[2]
    label = PROVIDER_LABELS.get(params.provider, params.provider)
    await callback.answer(label)
    await _generate_and_send(callback.message, params, image_service, balance_service, quota_service, user_id)


# ═══════════════════════════════════════════════════════
#  CORE
# ═══════════════════════════════════════════════════════

async def _generate_and_send(
    message: Message,
    params: ImageGenParams,
    image_service: ImageService,
    balance_service: BalanceService,
    quota_service: QuotaService | None = None,
    user_id: int | None = None,
):
    provider_label = PROVIDER_LABELS.get(params.provider, params.provider)
    waiting = await message.answer(f"{provider_label} генерирует изображение...")

    try:
        result = await image_service.generate(params)
    except Exception as e:
        logger.exception("Image generation failed")
        error_msg = str(e)[:500]
        if "content_policy" in error_msg.lower() or "safety" in error_msg.lower():
            await waiting.edit_text("Промпт отклонён политикой безопасности провайдера.")
        else:
            await waiting.edit_text(f"Ошибка генерации: {error_msg}")
        return

    # Track cost
    if balance_service:
        service_map = {"dalle": "openai", "imagen": "gemini", "flux": "bfl"}
        service_name = service_map.get(params.provider, params.provider)
        await balance_service.track_image_generation(service_name, result.cost)

    # Track image quota
    if quota_service and user_id:
        await quota_service.track_image_usage(user_id)

    # Delete waiting message
    await waiting.delete()

    # Caption
    caption = f"{provider_label} | {result.size} | ${result.cost:.2f}"
    if result.revised_prompt and result.revised_prompt != params.prompt:
        # Trim revised prompt for caption (Telegram caption limit = 1024)
        revised = result.revised_prompt[:200]
        if len(result.revised_prompt) > 200:
            revised += "..."
        caption += f"\n<i>{revised}</i>"

    # Keyboard
    keyboard = get_image_result_keyboard(
        current_provider=params.provider,
        current_size=params.size,
        current_style=params.style,
        current_quality=params.quality,
        available_providers=image_service.available_providers(),
    )

    # Send photo
    photo = BufferedInputFile(result.image_data, filename="generated.png")
    await message.answer_photo(
        photo=photo,
        caption=caption,
        parse_mode="HTML",
        reply_markup=keyboard,
    )
