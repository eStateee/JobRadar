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

    async def analyze_all(self) -> dict:
        logger.info("Starting analysis of raw vacancies...")
        
        # Get profile
        result = await self.session.execute(select(Profile).limit(1))
        profile = result.scalar_one_or_none()
        
        if not profile or not profile.resume_summary_json or not profile.filters_summary_json:
            logger.warning("Profile or filters not set. Skipping analysis.")
            return {"analyzed": 0, "rejected": 0, "errors": 0}
            
        profile_summary_str = json.dumps(profile.resume_summary_json, ensure_ascii=False)
        filters_summary_str = json.dumps(profile.filters_summary_json, ensure_ascii=False)

        # Get raw vacancies
        vacancies_result = await self.session.execute(
            select(Vacancy).where(Vacancy.status == VacancyStatus.raw)
        )
        vacancies = vacancies_result.scalars().all()
        
        stats = {"analyzed": 0, "rejected": 0, "errors": 0}
        
        for vac in vacancies:
            logger.info(f"Вакансия #{vac.id} отправлена на анализ")
            try:
                analysis = await analyze_vacancy(vac.raw_text, profile_summary_str, filters_summary_str)
                
                if not analysis.is_vacancy:
                    vac.status = VacancyStatus.rejected
                    stats["rejected"] += 1
                    logger.info(f"Вердикт AI: Вакансия #{vac.id} - Match Score = 0%, Status = Rejected")
                else:
                    vac.status = VacancyStatus.analyzed
                    vac.match_score = analysis.match_score
                    vac.match_reason = analysis.match_reason
                    vac.extracted_data = analysis.model_dump()
                    stats["analyzed"] += 1
                    logger.info(f"Вердикт AI: Вакансия #{vac.id} - Match Score = {analysis.match_score}%, Status = Analyzed")
                    
            except Exception as e:
                logger.error(f"Error analyzing vacancy {vac.id}: {e}")
                vac.status = VacancyStatus.error
                stats["errors"] += 1
                
            await self.session.commit()
            
        return stats

    async def notify_all(self) -> int:
        from core.notifier import Notifier
        from bot.main_bot import bot
        notifier = Notifier(self.session, bot)
        return await notifier.notify_all()

    async def run_full_pipeline(self) -> dict:
        collected = await self.collect_all()
        analysis_stats = await self.analyze_all()
        notified = await self.notify_all()
        
        notified_count = notified or 0
        
        logger.info(
            "=== Итоги цикла пайплайна ===\n"
            f"Собрано новых: {collected}\n"
            f"Проанализировано: {analysis_stats.get('analyzed', 0)}\n"
            f"Отсеяно: {analysis_stats.get('rejected', 0)}\n"
            f"Ошибок: {analysis_stats.get('errors', 0)}\n"
            f"Отправлено уведомлений: {notified_count}"
        )
        
        return {
            "collected": collected,
            "analyzed": analysis_stats.get('analyzed', 0),
            "notified": notified_count
        }
