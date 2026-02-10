from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from bot.keyboards.model_select import get_model_keyboard
from bot.services.ai_router import AIRouter

router = Router()


@router.message(Command("model"))
@router.message(F.text == "Модель")
async def cmd_model(message: Message, ai_router: AIRouter):
    user_id = message.from_user.id
    current = await ai_router.load_user_provider(user_id)
    available = ai_router.available_providers()

    await message.answer(
        "Выбери модель:",
        reply_markup=get_model_keyboard(available, current, ai_router.model_versions()),
    )


@router.callback_query(F.data == "model:close")
async def on_model_close(callback: CallbackQuery):
    await callback.answer()
    await callback.message.delete()


@router.callback_query(F.data.startswith("model:"))
async def on_model_select(callback: CallbackQuery, ai_router: AIRouter):
    provider = callback.data.split(":")[1]
    user_id = callback.from_user.id

    if provider == "all":
        await ai_router.save_user_provider(user_id, "all")
        await callback.message.edit_text(
            "Режим: Спросить ВСЕХ\n"
            "Следующее сообщение получат все 3 модели."
        )
    elif provider in ai_router.services:
        await ai_router.save_user_provider(user_id, provider)
        display = ai_router.get_display_name(provider)
        await callback.message.edit_text(
            f"Модель переключена на {display}"
        )
    else:
        await callback.answer("Модель недоступна", show_alert=True)

    await callback.answer()
