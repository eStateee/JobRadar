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
        "/reset_channels - Сбросить состояние сбора (начнет сбор истории заново)\n"
        "\n<i>Для настройки профиля и фильтров отправьте текстовый файл (.txt).</i>"
    )
    await message.answer(text)

@router.message(Command("reset_channels"))
async def cmd_reset_channels(message: Message):
    from db.database import async_session
    from db.models import Channel
    from sqlalchemy import update
    
    try:
        async with async_session() as session:
            await session.execute(
                update(Channel).values(
                    backfill_completed=False,
                    last_collected_message_id=None
                )
            )
            await session.commit()
        await message.answer("✅ <b>Успешно:</b> Состояние всех каналов сброшено. При следующем /run история за 14 дней будет собрана заново.")
    except Exception as e:
        await message.answer(f"❌ Ошибка при сбросе каналов: {e}")
