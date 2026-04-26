import logging
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import Vacancy, VacancyStatus, Profile
from core.collector import TelegramCollector
from core.analyzer import analyze_vacancy

logger = logging.getLogger(__name__)

class Pipeline:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def collect_all(self) -> int:
        collector = TelegramCollector(self.session)
        return await collector.run()

    async def analyze_all(self) -> int:
        logger.info("Starting analysis of raw vacancies...")
        
        # Get profile
        result = await self.session.execute(select(Profile).limit(1))
        profile = result.scalar_one_or_none()
        
        if not profile or not profile.resume_summary_json or not profile.filters_summary_json:
            logger.warning("Profile or filters not set. Skipping analysis.")
            return 0
            
        profile_summary_str = json.dumps(profile.resume_summary_json, ensure_ascii=False)
        filters_summary_str = json.dumps(profile.filters_summary_json, ensure_ascii=False)

        # Get raw vacancies
        vacancies_result = await self.session.execute(
            select(Vacancy).where(Vacancy.status == VacancyStatus.raw)
        )
        vacancies = vacancies_result.scalars().all()
        
        analyzed_count = 0
        
        for vac in vacancies:
            try:
                analysis = await analyze_vacancy(vac.raw_text, profile_summary_str, filters_summary_str)
                
                if not analysis.is_vacancy:
                    vac.status = VacancyStatus.rejected
                else:
                    vac.status = VacancyStatus.analyzed
                    vac.match_score = analysis.match_score
                    vac.match_reason = analysis.match_reason
                    vac.extracted_data = analysis.model_dump()
                    
                analyzed_count += 1
            except Exception as e:
                logger.error(f"Error analyzing vacancy {vac.id}: {e}")
                vac.status = VacancyStatus.error
                
            await self.session.commit()
            
        return analyzed_count

    async def notify_all(self) -> int:
        from core.notifier import Notifier
        from bot.main_bot import bot
        notifier = Notifier(self.session, bot)
        return await notifier.notify_all()

    async def run_full_pipeline(self) -> dict:
        collected = await self.collect_all()
        analyzed = await self.analyze_all()
        notified = await self.notify_all()
        return {
            "collected": collected,
            "analyzed": analyzed,
            "notified": notified or 0
        }
