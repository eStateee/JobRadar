import logging
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from bot.keyboards.reply import get_main_menu

logger = logging.getLogger(__name__)

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    text = (
        "👋 <b>Добро пожаловать в JobRadar!</b>\n\n"
        "Я AI-бот рекрутер. Я могу искать вакансии в Telegram-каналах "
        "и анализировать их на соответствие вашему профилю.\n\n"
        "Используйте меню ниже для навигации."
    )
    await message.answer(text, reply_markup=get_main_menu())

@router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "ℹ️ <b>Справка:</b>\n"
        "👤 <b>Профиль</b> - Загрузите резюме и фильтры.\n"
        "📢 <b>Каналы</b> - Управление списком Telegram-каналов для поиска.\n"
        "📊 <b>Статус</b> - Текущее состояние базы данных (очередь, обработанные).\n"
        "🚀 <b>Запуск</b> - Ручной запуск пайплайна (сбор, анализ, рассылка).\n\n"
        "Если вы застряли при вводе данных, используйте кнопку ❌ Отмена или команду /cancel."
    )
    await message.answer(text, reply_markup=get_main_menu())

@router.message(Command("cancel"))
@router.message(F.text.lower().in_(["отмена", "❌ отмена"]))
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нет активных действий для отмены.", reply_markup=get_main_menu())
        return

    logger.info(f"Cancelling state {current_state}")
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=get_main_menu())
