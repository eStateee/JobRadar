import logging
import io
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.database import async_session
from db.models import Profile
from core.analyzer import extract_profile, extract_filters, update_filters
from core.schemas import SearchFilters

logger = logging.getLogger(__name__)

router = Router()

async def get_or_create_profile(session: AsyncSession) -> Profile:
    result = await session.execute(select(Profile).limit(1))
    profile = result.scalar_one_or_none()
    if not profile:
        profile = Profile()
        session.add(profile)
        await session.commit()
    return profile

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    async with async_session() as session:
        profile = await get_or_create_profile(session)
        
    resume_text = "Не загружено"
    if profile.resume_summary_json:
        resume_text = (
            f"Роли: {', '.join(profile.resume_summary_json.get('roles', []))}\n"
            f"Навыки: {', '.join(profile.resume_summary_json.get('skills', []))}\n"
            f"Опыт: {profile.resume_summary_json.get('experience_years')} лет\n"
        )
        
    filters_text = "Не загружено"
    if profile.filters_summary_json:
        filters = profile.filters_summary_json
        filters_text = (
            f"Форматы: {', '.join(filters.get('formats', []))}\n"
            f"ЗП от: {filters.get('min_salary')} {filters.get('currency')}\n"
            f"Обязательно: {', '.join(filters.get('must_have_skills', []))}\n"
            f"Исключить: {', '.join(filters.get('excluded_keywords', []))}"
        )
        
    text = (
        "<b>Ваш профиль:</b>\n\n"
        f"<b>Резюме:</b>\n{resume_text}\n\n"
        f"<b>Фильтры поиска:</b>\n{filters_text}\n\n"
        f"<i>Min Match Score:</i> {profile.min_match_score}"
    )
    await message.answer(text)

@router.message(F.document)
async def handle_document(message: Message):
    if not message.document.file_name.endswith('.txt'):
        await message.answer("Пожалуйста, загружайте только .txt файлы.")
        return
        
    file_id = message.document.file_id
    file = await message.bot.get_file(file_id)
    file_path = file.file_path
    downloaded_file = await message.bot.download_file(file_path)
    content = downloaded_file.read().decode('utf-8')
    
    caption = (message.caption or "").lower()
    file_name = message.document.file_name.lower()
    
    msg = await message.answer("Анализирую файл...")
    
    if "resume" in caption or "резюме" in caption or "resume" in file_name or "резюме" in file_name:
        try:
            summary = await extract_profile(content)
            async with async_session() as session:
                profile = await get_or_create_profile(session)
                profile.resume_raw_text = content
                profile.resume_summary_json = summary.model_dump()
                await session.commit()
            await msg.edit_text("Резюме успешно обработано и сохранено!")
        except Exception as e:
            logger.error(f"Failed to process resume: {e}")
            await msg.edit_text("Ошибка при обработке резюме.")
            
    elif "filter" in caption or "фильтр" in caption or "filter" in file_name or "пожелани" in file_name:
        try:
            filters = await extract_filters(content)
            async with async_session() as session:
                profile = await get_or_create_profile(session)
                profile.filters_raw_text = content
                profile.filters_summary_json = filters.model_dump()
                await session.commit()
            await msg.edit_text("Фильтры успешно обработаны и сохранены!")
        except Exception as e:
            logger.error(f"Failed to process filters: {e}")
            await msg.edit_text("Ошибка при обработке фильтров.")
    else:
        await msg.edit_text("Не удалось определить тип файла. Пожалуйста, добавьте подпись 'resume' или 'filter'.")

@router.message(F.text & ~F.text.startswith('/'))
async def handle_text_filter_update(message: Message):
    # If text is not a command and not a channel (handled in channels.py)
    if message.text.startswith('@') or 't.me/' in message.text:
        return # Let channels router handle it
        
    msg = await message.answer("Обновляю фильтры...")
    
    async with async_session() as session:
        profile = await get_or_create_profile(session)
        if not profile.filters_summary_json:
            await msg.edit_text("У вас еще нет фильтров. Загрузите их сначала файлом.")
            return
            
        current_filters = SearchFilters(**profile.filters_summary_json)
        
        try:
            updated_filters = await update_filters(current_filters, message.text)
            profile.filters_summary_json = updated_filters.model_dump()
            await session.commit()
            await msg.edit_text("Фильтры успешно обновлены! Проверьте через /profile")
        except Exception as e:
            logger.error(f"Failed to update filters: {e}")
            await msg.edit_text("Ошибка при обновлении фильтров.")
