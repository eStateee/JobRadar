import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from bot.config import config
from bot.middlewares.allowlist import AllowlistMiddleware

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

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
    from bot.handlers import admin, channels, pipeline_cmds, profile
    dp.include_router(admin.router)
    dp.include_router(channels.router)
    dp.include_router(pipeline_cmds.router)
    dp.include_router(profile.router)

def init_bot():
    setup_routers()
    return bot, dp
