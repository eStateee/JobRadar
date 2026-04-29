from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu() -> ReplyKeyboardMarkup:
    """Генерирует главное меню бота."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="👤 Профиль"),
                KeyboardButton(text="📢 Каналы")
            ],
            [
                KeyboardButton(text="📊 Статус"),
                KeyboardButton(text="🚀 Запуск")
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )

def get_cancel_menu() -> ReplyKeyboardMarkup:
    """Генерирует меню с кнопкой отмены."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )
