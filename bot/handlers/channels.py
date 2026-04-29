import httpx
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.database import async_session
from db.models import Channel
from bot.config import config
import logging
from bot.keyboards.inline import get_channel_inline_keyboard, get_add_channel_menu
from bot.keyboards.reply import get_cancel_menu, get_main_menu

logger = logging.getLogger(__name__)

router = Router()

class ChannelState(StatesGroup):
    waiting_for_channel = State()

async def check_channel_exists(username: str) -> bool:
    url = f"https://t.me/s/{username}"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            return response.status_code == 200
    except httpx.RequestError as e:
        logger.error(f"Error checking channel {username}: {e}")
        return False

@router.message(Command("channels"))
@router.message(F.text == "📢 Каналы")
async def cmd_channels(message: Message, state: FSMContext):
    await state.clear()
    async with async_session() as session:
        result = await session.execute(select(Channel))
        channels = result.scalars().all()

    if not channels:
        await message.answer(
            "Список каналов пуст.\n"
            "Нажмите кнопку ниже, чтобы добавить канал.",
            reply_markup=get_add_channel_menu()
        )
        return

    text = "<b>Список каналов:</b>\n\n"
    for ch in channels:
        status = "✅ Вкл" if ch.is_active else "❌ Выкл"
        text += f"• @{ch.username} - {status}\n"
        
        await message.answer(f"@{ch.username}", reply_markup=get_channel_inline_keyboard(ch.id))

    await message.answer("Управление каналами:", reply_markup=get_add_channel_menu())

@router.callback_query(F.data.startswith("toggle_"))
async def process_toggle(callback: CallbackQuery):
    channel_id = int(callback.data.split("_")[1])
    async with async_session() as session:
        channel = await session.get(Channel, channel_id)
        if channel:
            channel.is_active = not channel.is_active
            await session.commit()
            status = "✅ Вкл" if channel.is_active else "❌ Выкл"
            await callback.message.edit_text(f"@{channel.username} - {status}", reply_markup=callback.message.reply_markup)
            await callback.answer(f"Статус изменен")
        else:
            await callback.answer("Канал не найден", show_alert=True)

@router.callback_query(F.data.startswith("delete_"))
async def process_delete(callback: CallbackQuery):
    channel_id = int(callback.data.split("_")[1])
    async with async_session() as session:
        channel = await session.get(Channel, channel_id)
        if channel:
            await session.delete(channel)
            await session.commit()
            await callback.message.delete()
            await callback.answer("Канал удален")
        else:
            await callback.answer("Канал не найден", show_alert=True)

@router.callback_query(F.data == "add_channel")
async def process_add_channel_btn(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ChannelState.waiting_for_channel)
    await callback.message.answer(
        "➕ <b>Добавление канала</b>\n\n"
        "Отправьте юзернейм или ссылку (например: @it_jobs_ru или https://t.me/it_jobs_ru).",
        reply_markup=get_cancel_menu()
    )
    await callback.answer()

@router.message(ChannelState.waiting_for_channel, F.text)
async def process_new_channel(message: Message, state: FSMContext):
    text = message.text.strip()
    username = None
    
    if text.startswith('@'):
        username = text[1:]
    elif 't.me/' in text:
        username = text.split('t.me/')[-1].split('/')[0]
    elif 't.me/s/' in text:
        username = text.split('t.me/s/')[-1].split('/')[0]
        
    if not username:
        await message.answer("❌ Неверный формат. Попробуйте еще раз или нажмите Отмена.")
        return

    msg = await message.answer(f"⏳ Проверяю канал @{username}...")
    
    exists = await check_channel_exists(username)
    if not exists:
        await msg.edit_text(f"❌ Канал @{username} не найден или закрыт (приватный).", reply_markup=get_main_menu())
        await state.clear()
        return
        
    async with async_session() as session:
        result = await session.execute(select(Channel).where(Channel.username == username))
        existing = result.scalar_one_or_none()
        if existing:
            await msg.edit_text(f"⚠️ Канал @{username} уже в списке!", reply_markup=get_main_menu())
            await state.clear()
            return
            
        new_channel = Channel(
            username=username,
            is_active=True
        )
        session.add(new_channel)
        await session.commit()
        
    await msg.edit_text(f"✅ Канал @{username} успешно добавлен!", reply_markup=get_main_menu())
    await state.clear()
