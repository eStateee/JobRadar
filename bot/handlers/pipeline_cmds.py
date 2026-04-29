from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from db.database import async_session
from core.collector import TelegramCollector
import logging

logger = logging.getLogger(__name__)

router = Router()

@router.message(Command("test_parse"))
async def cmd_test_parse(message: Message):
    msg = await message.answer("⏳ Запускаю парсинг каналов...")
    
    try:
        async with async_session() as session:
            from core.pipeline import Pipeline
            pipeline = Pipeline(session)
            new_posts = await pipeline.collect_all()
        
        await msg.edit_text(f"✅ Парсинг завершен. Собрано {new_posts} новых постов.")
    except Exception as e:
        logger.error(f"Parse error: {e}")
        await msg.edit_text(f"❌ Ошибка парсинга: {e}")

@router.message(Command("test_analyze"))
async def cmd_test_analyze(message: Message):
    msg = await message.answer("⏳ Запускаю анализ сырых вакансий...")
    
    try:
        async with async_session() as session:
            from core.pipeline import Pipeline
            pipeline = Pipeline(session)
            analyzed_count = await pipeline.analyze_all()
        
        await msg.edit_text(f"✅ Анализ завершен. Проанализировано {analyzed_count} постов.")
    except Exception as e:
        logger.error(f"Analyze error: {e}")
        await msg.edit_text(f"❌ Ошибка анализа: {e}")

@router.message(Command("test_notify"))
async def cmd_test_notify(message: Message):
    msg = await message.answer("⏳ Запускаю отправку уведомлений...")
    try:
        async with async_session() as session:
            from core.pipeline import Pipeline
            pipeline = Pipeline(session)
            sent_count = await pipeline.notify_all()
        await msg.edit_text(f"✅ Отправка завершена. Отправлено {sent_count} сообщений.")
    except Exception as e:
        logger.error(f"Notify error: {e}")
        await msg.edit_text(f"❌ Ошибка отправки: {e}")

@router.message(Command("run"))
@router.message(F.text == "🚀 Запуск")
async def cmd_run(message: Message):
    msg = await message.answer("⏳ <b>Запускаю полный цикл (Сбор ➡️ Анализ ➡️ Отправка)...</b>\n<i>Это может занять несколько минут.</i>")
    try:
        async with async_session() as session:
            from core.pipeline import Pipeline
            pipeline = Pipeline(session)
            res = await pipeline.run_full_pipeline()
        
        await msg.edit_text(
            f"✅ <b>Цикл успешно завершен!</b>\n\n"
            f"📥 Собрано новых постов: {res['collected']}\n"
            f"🧠 Проанализировано: {res['analyzed']}\n"
            f"📤 Отправлено уведомлений: {res['notified']}"
        )
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        await msg.edit_text(f"❌ Ошибка пайплайна: {e}")

@router.message(Command("status"))
@router.message(F.text == "📊 Статус")
async def cmd_status(message: Message):
    try:
        from db.models import Channel, Vacancy, VacancyStatus
        from sqlalchemy import func
        from sqlalchemy import select
        async with async_session() as session:
            channels_count = await session.scalar(select(func.count(Channel.id)))
            raw_count = await session.scalar(select(func.count(Vacancy.id)).where(Vacancy.status == VacancyStatus.raw))
            analyzed_count = await session.scalar(select(func.count(Vacancy.id)).where(Vacancy.status == VacancyStatus.analyzed))
            sent_count = await session.scalar(select(func.count(Vacancy.id)).where(Vacancy.status == VacancyStatus.sent))
            error_count = await session.scalar(select(func.count(Vacancy.id)).where(Vacancy.status == VacancyStatus.error))
            
            await message.answer(
                "📊 <b>Статус системы:</b>\n\n"
                f"📢 <b>Источники (Каналы):</b> {channels_count}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📥 <b>В очереди на анализ:</b> {raw_count}\n"
                f"🧠 <b>Проанализировано (не подошли):</b> {analyzed_count}\n"
                f"📤 <b>Отправлено вам:</b> {sent_count}\n"
                f"❌ <b>С ошибками:</b> {error_count}"
            )
    except Exception as e:
        logger.error(f"Status error: {e}")
        await message.answer(f"❌ Ошибка получения статуса: {e}")

@router.message(Command("errors"))
async def cmd_errors(message: Message):
    try:
        from db.models import Vacancy, VacancyStatus
        from sqlalchemy import select
        async with async_session() as session:
            result = await session.execute(
                select(Vacancy)
                .where(Vacancy.status == VacancyStatus.error)
                .order_by(Vacancy.posted_at.desc())
                .limit(5)
            )
            errors = result.scalars().all()
            
            if not errors:
                await message.answer("Ошибок не найдено ✅")
                return
                
            text = "⚠️ <b>Последние 5 ошибок:</b>\n\n"
            for e in errors:
                text += f"ID: {e.id} | <a href='{e.post_url}'>Пост</a>\n"
            await message.answer(text)
    except Exception as e:
        logger.error(f"Errors command failed: {e}")
        await message.answer(f"❌ Ошибка: {e}")
