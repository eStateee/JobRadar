import logging
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import Vacancy, VacancyStatus, Profile
from bot.config import config

logger = logging.getLogger(__name__)

class Notifier:
    def __init__(self, session: AsyncSession, bot: Bot):
        self.session = session
        self.bot = bot
        self.admin_id = config.admin_tg_id
        self.batch_limit = 10

    def format_message(self, vac: Vacancy) -> str:
        data = vac.extracted_data or {}
        role = data.get("role", "Не указана")
        salary = data.get("salary", "Не указана")
        format_work = data.get("format", "Не указан")
        score = vac.match_score
        reason = vac.match_reason or "Нет описания"
        
        # Build message
        text = (
            f"🎯 <b>Матч: {score}%</b>\n\n"
            f"💼 <b>Роль:</b> {role}\n"
            f"💰 <b>ЗП:</b> {salary}\n"
            f"📍 <b>Формат:</b> {format_work}\n\n"
            f"🤔 <b>Почему подходит:</b>\n{reason}\n\n"
            f"🔗 <a href='{vac.post_url}'>Ссылка на пост</a>"
        )
        return text

    async def notify_all(self) -> int:
        result = await self.session.execute(select(Profile).limit(1))
        profile = result.scalar_one_or_none()
        min_score = profile.min_match_score if profile else 70

        # Select analyzed vacancies above min_score
        vacancies_result = await self.session.execute(
            select(Vacancy)
            .where(Vacancy.status == VacancyStatus.analyzed)
            .where(Vacancy.match_score >= min_score)
            .limit(self.batch_limit)
        )
        vacancies = vacancies_result.scalars().all()
        
        sent_count = 0
        
        for vac in vacancies:
            text = self.format_message(vac)
            try:
                await self.bot.send_message(chat_id=self.admin_id, text=text, disable_web_page_preview=True)
                vac.status = VacancyStatus.sent
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send vacancy {vac.id}: {e}")
                
            await self.session.commit()
            
        return sent_count
