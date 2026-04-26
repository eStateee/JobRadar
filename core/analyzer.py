from pydantic_ai import Agent, RunContext
from core.schemas import ProfileSummary, SearchFilters, VacancyAnalysisResult
from bot.config import config
import logging

logger = logging.getLogger(__name__)

# Config the LLM provider
llm_model_name = config.llm_model

profile_agent = Agent(
    llm_model_name,
    result_type=ProfileSummary,
    system_prompt=(
        "Ты профессиональный IT-рекрутер. Твоя задача извлечь структурированную информацию "
        "из текста резюме (роли, навыки, опыт, краткое саммари)."
    ),
    retries=3
)

filters_agent = Agent(
    llm_model_name,
    result_type=SearchFilters,
    system_prompt=(
        "Ты IT-рекрутер. Твоя задача извлечь структурированные пожелания кандидата по поиску работы "
        "(форматы работы, мин. зарплата, валюта, обязательные навыки, исключаемые слова)."
    ),
    retries=3
)

filters_update_agent = Agent(
    llm_model_name,
    result_type=SearchFilters,
    system_prompt=(
        "Ты IT-рекрутер. У тебя есть текущие фильтры поиска (SearchFilters). Пользователь прислал "
        "новое пожелание (например, 'хочу только удаленку'). Обнови текущие фильтры, сохраняя остальные."
    ),
    retries=3
)

vacancy_agent = Agent(
    llm_model_name,
    result_type=VacancyAnalysisResult,
    system_prompt=(
        "Ты IT-рекрутер. Твоя задача проанализировать пост из Telegram канала. "
        "Сначала определи, является ли это вакансией (не реклама, не новость). "
        "Если это вакансия, извлеки роль, зарплату, формат. "
        "Затем сравни вакансию с профилем кандидата и его фильтрами поиска. "
        "Оцени релевантность (match_score от 0 до 100). "
        "ВАЖНОЕ ПРАВИЛО: Отсутствие зарплаты в вакансии не должно занижать скор, если стек и роль подходят! "
        "Опиши причину (match_reason)."
    ),
    retries=3
)

async def extract_profile(text: str) -> ProfileSummary:
    result = await profile_agent.run(text)
    return result.data

async def extract_filters(text: str) -> SearchFilters:
    result = await filters_agent.run(text)
    return result.data

async def update_filters(current_filters: SearchFilters, update_text: str) -> SearchFilters:
    prompt = f"Текущие фильтры: {current_filters.model_dump_json()}\nПожелание: {update_text}"
    result = await filters_update_agent.run(prompt)
    return result.data

async def analyze_vacancy(post_text: str, profile_summary: str, filters_summary: str) -> VacancyAnalysisResult:
    prompt = (
        f"Профиль кандидата: {profile_summary}\n"
        f"Фильтры кандидата: {filters_summary}\n"
        f"Текст поста:\n{post_text}"
    )
    result = await vacancy_agent.run(prompt)
    return result.data
