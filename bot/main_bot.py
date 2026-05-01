import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import ErrorEvent
from bot.config import config
from bot.middlewares.allowlist import AllowlistMiddleware

logger = logging.getLogger(__name__)

# Initialize Bot
bot = Bot(
    token=config.bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

# Initialize Dispatcher
dp = Dispatcher()

# Register global middlewares
dp.message.middleware(AllowlistMiddleware(config.admin_tg_id))
dp.callback_query.middleware(AllowlistMiddleware(config.admin_tg_id))

def setup_routers():
    from bot.handlers import admin, channels, pipeline_cmds, profile, common
    # Регистрируем общие команды (start, cancel)
    dp.include_router(common.router)
    # Административные команды
    dp.include_router(admin.router)
    # Команды профиля
    dp.include_router(profile.router)
    # Команды пайплайна (run, status)
    dp.include_router(pipeline_cmds.router)
    # Роутер каналов должен быть последним, если он перехватывает текст
    dp.include_router(channels.router)

def init_bot():
    setup_routers()
    
    # Глобальный обработчик ошибок
    @dp.errors()
    async def global_error_handler(event: ErrorEvent):
        logger.error(
            f"Необработанная ошибка Aiogram: {event.exception}",
            exc_info=event.exception
        )

    return bot, dp
