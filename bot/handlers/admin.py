from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("Привет, я твой AI-рекрутер! Готов к работе. Введи /help для списка команд.")

@router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "<b>Доступные команды:</b>\n\n"
        "/channels - Управление каналами\n"
        "/profile - Настройки профиля и фильтров\n"
        "/run - Запустить пайплайн (Сбор -> Анализ -> Отправка)\n"
        "/status - Статистика системы\n"
        "/errors - Последние ошибки\n"
        "\n<i>Для настройки профиля и фильтров отправьте текстовый файл (.txt).</i>"
    )
    await message.answer(text)
