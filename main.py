import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bot.main_bot import init_bot
from db.database import init_db, async_session

async def scheduled_pipeline():
    try:
        async with async_session() as session:
            from core.pipeline import Pipeline
            pipeline = Pipeline(session)
            await pipeline.run_full_pipeline()
    except Exception as e:
        logging.error(f"Scheduled pipeline error: {e}")

async def main():
    logger = logging.getLogger(__name__)
    logger.info("Initializing database...")
    await init_db()
    
    logger.info("Starting bot...")
    bot, dp = init_bot()
    
    logger.info("Starting scheduler...")
    scheduler = AsyncIOScheduler()
    # Currently running every 6 hours as a default fallback. 
    # Can be configured to use schedule_times from Profile DB in a more advanced way.
    scheduler.add_job(scheduled_pipeline, 'interval', hours=6)
    scheduler.start()
    
    # Drop pending updates and start polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")
