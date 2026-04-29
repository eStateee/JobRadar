from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_profile_inline_menu() -> InlineKeyboardMarkup:
    """Инлайн-кнопки для профиля."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="❔ Как заполнить профиль?", callback_data="help_profile")
            ],
            [
                InlineKeyboardButton(text="✏️ Обновить фильтры текстом", callback_data="update_filters_text")
            ]
        ]
    )

def get_channel_inline_keyboard(channel_id: int) -> InlineKeyboardMarkup:
    """Инлайн-кнопки для управления каналом."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Вкл/Выкл", callback_data=f"toggle_{channel_id}"),
                InlineKeyboardButton(text="Удалить", callback_data=f"delete_{channel_id}")
            ]
        ]
    )

def get_add_channel_menu() -> InlineKeyboardMarkup:
    """Кнопка добавления канала."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Добавить канал", callback_data="add_channel")
            ]
        ]
    )
