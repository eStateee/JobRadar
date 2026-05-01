import logging
import io
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup, default_state
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.database import async_session
from db.models import Profile
from core.analyzer import extract_profile, extract_filters, update_filters
from core.schemas import SearchFilters
from bot.keyboards.inline import get_profile_inline_menu
from bot.keyboards.reply import get_cancel_menu, get_main_menu

logger = logging.getLogger(__name__)

router = Router()

class ProfileState(StatesGroup):
    waiting_for_filter_update = State()

async def get_or_create_profile(session: AsyncSession) -> Profile:
    result = await session.execute(select(Profile).limit(1))
    profile = result.scalar_one_or_none()
    if not profile:
        profile = Profile()
        session.add(profile)
        await session.commit()
    return profile

@router.message(Command("profile"))
@router.message(F.text == "👤 Профиль")
async def cmd_profile(message: Message, state: FSMContext):
    await state.clear()
    async with async_session() as session:
        profile = await get_or_create_profile(session)
        
    resume_text = "❌ <b>Не загружено</b>\n<i>Отправьте .txt файл с подписью 'resume'</i>"
    if profile.resume_summary_json:
        resume_text = (
            f"✅ <b>Загружено</b>\n"
            f"Роли: {', '.join(profile.resume_summary_json.get('roles', []))}\n"
            f"Навыки: {', '.join(profile.resume_summary_json.get('skills', []))}\n"
            f"Опыт: {profile.resume_summary_json.get('experience_years')} лет\n"
        )
        
    filters_text = "❌ <b>Не загружено</b>\n<i>Отправьте .txt файл с подписью 'filter'</i>"
    if profile.filters_summary_json:
        filters = profile.filters_summary_json
        filters_text = (
            f"✅ <b>Загружено</b>\n"
            f"Форматы: {', '.join(filters.get('formats', []))}\n"
            f"ЗП от: {filters.get('min_salary')} {filters.get('currency')}\n"
            f"Обязательно: {', '.join(filters.get('must_have_skills', []))}\n"
            f"Исключить: {', '.join(filters.get('excluded_keywords', []))}"
        )
        
    text = (
        "👤 <b>Ваш профиль:</b>\n\n"
        f"<b>Резюме:</b>\n{resume_text}\n\n"
        f"<b>Фильтры поиска:</b>\n{filters_text}\n\n"
        f"<i>Min Match Score:</i> {profile.min_match_score}"
    )
    await message.answer(text, reply_markup=get_profile_inline_menu())

@router.callback_query(F.data == "help_profile")
async def process_help_profile(callback: CallbackQuery):
    help_text = (
        "ℹ️ <b>Как заполнить профиль?</b>\n\n"
        "1. <b>Резюме:</b> Сохраните ваше резюме в текстовый файл (.txt) и отправьте его боту. "
        "В подписи к файлу напишите слово <code>resume</code>.\n\n"
        "2. <b>Фильтры:</b> Создайте текстовый файл с вашими пожеланиями (формат работы, зарплата, "
        "обязательные навыки, слова-исключения). Отправьте его боту с подписью <code>filter</code>.\n\n"
        "Вы также можете обновлять фильтры текстовым сообщением, нажав кнопку 'Обновить фильтры текстом'."
    )
    await callback.message.answer(help_text)
    await callback.answer()

@router.callback_query(F.data == "update_filters_text")
async def process_update_filters_btn(callback: CallbackQuery, state: FSMContext):
    async with async_session() as session:
        profile = await get_or_create_profile(session)
        if not profile.filters_summary_json:
            await callback.answer("Сначала загрузите базовые фильтры файлом!", show_alert=True)
            return

    await state.set_state(ProfileState.waiting_for_filter_update)
    await callback.message.answer(
        "✍️ <b>Обновление фильтров</b>\n\n"
        "Напишите, что вы хотите изменить (например: 'увеличь зп до 200к' или 'добавь python в обязательные навыки').",
        reply_markup=get_cancel_menu()
    )
    await callback.answer()

@router.message(F.document, StateFilter(default_state))
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
    file_size = message.document.file_size or 0
    
    msg = await message.answer("⏳ Анализирую файл...")
    
    if "resume" in caption or "резюме" in caption or "resume" in file_name or "резюме" in file_name:
        logger.info(f"File upload detected. Inferred type: RESUME. Name: {file_name}, Size: {file_size} bytes")
        try:
            summary = await extract_profile(content)
            async with async_session() as session:
                profile = await get_or_create_profile(session)
                profile.resume_raw_text = content
                profile.resume_summary_json = summary.model_dump()
                await session.commit()
            await msg.edit_text("✅ Резюме успешно обработано и сохранено!")
        except Exception as e:
            logger.error(f"Failed to process resume: {e}")
            await msg.edit_text("❌ Ошибка при обработке резюме.")
            
    elif "filter" in caption or "фильтр" in caption or "filter" in file_name or "пожелани" in file_name:
        logger.info(f"File upload detected. Inferred type: FILTER. Name: {file_name}, Size: {file_size} bytes")
        try:
            filters = await extract_filters(content)
            async with async_session() as session:
                profile = await get_or_create_profile(session)
                profile.filters_raw_text = content
                profile.filters_summary_json = filters.model_dump()
                await session.commit()
            await msg.edit_text("✅ Фильтры успешно обработаны и сохранены!")
        except Exception as e:
            logger.error(f"Failed to process filters: {e}")
            await msg.edit_text("❌ Ошибка при обработке фильтров.")
    else:
        await msg.edit_text("❌ Не удалось определить тип файла. Пожалуйста, добавьте подпись 'resume' или 'filter'.")

@router.message(ProfileState.waiting_for_filter_update, F.text)
async def handle_text_filter_update(message: Message, state: FSMContext):
    msg = await message.answer("⏳ Обновляю фильтры...")
    
    async with async_session() as session:
        profile = await get_or_create_profile(session)
        if not profile.filters_summary_json:
            await msg.delete()
            await message.answer("У вас еще нет фильтров. Загрузите их сначала файлом.", reply_markup=get_main_menu())
            await state.clear()
            return
            
        current_filters = SearchFilters(**profile.filters_summary_json)
        
        try:
            updated_filters = await update_filters(current_filters, message.text)
            profile.filters_summary_json = updated_filters.model_dump()
            await session.commit()
            await msg.delete()
            await message.answer("✅ Фильтры успешно обновлены! Проверьте через /profile", reply_markup=get_main_menu())
            await state.clear()
        except Exception as e:
            logger.error(f"Failed to update filters: {e}")
            await msg.delete()
            await message.answer("❌ Ошибка при обновлении фильтров.", reply_markup=get_main_menu())
            await state.clear()
