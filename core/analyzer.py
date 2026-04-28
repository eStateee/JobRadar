import logging
import json
import re
from openai import AsyncOpenAI
from core.schemas import ProfileSummary, SearchFilters, VacancyAnalysisResult
from bot.config import config

logger = logging.getLogger(__name__)

client = AsyncOpenAI(
    api_key=config.llm_api_key,
    base_url=config.llm_base_url
)

def clean_json_string(text: str) -> str:
    """Удаляет лишний текст и markdown-разметку."""
    # Убираем блоки кода ```json ... ```
    text = re.sub(r"```json\s?|\s?```", "", text).strip()
    # Если модель все равно налила текста ДО или ПОСЛЕ JSON, пытаемся вырезать только сам объект
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        return match.group(1)
    return text

async def get_llm_response(system_prompt: str, user_prompt: str, response_model):
    """Универсальная функция запроса к LLM с жестким принуждением к JSON."""
    
    schema = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
    
    # Максимально строгий промпт
    full_system_prompt = (
        f"{system_prompt}\n"
        "ИНСТРУКЦИЯ ПО ВЫВОДУ:\n"
        "1. ВЫВОДИ ТОЛЬКО ЧИСТЫЙ JSON.\n"
        "2. НЕ ПИШИ НИКАКИХ ПОЯСНЕНИЙ, СОВЕТОВ ИЛИ ВОПРОСОВ.\n"
        "3. НЕ ИСПОЛЬЗУЙ СВОИ ПОЛЯ, ТОЛЬКО ПОЛЯ ИЗ СХЕМЫ.\n"
        f"4. СТРОГО СОБЛЮДАЙ ЭТУ СХЕМУ: {schema}"
    )
    
    try:
        response = await client.chat.completions.create(
            model=config.llm_model,
            messages=[
                {"role": "system", "content": full_system_prompt},
                {"role": "user", "content": f"ОБРАБОТАЙ ЭТОТ ТЕКСТ И ВЫДАЙ JSON: \n\n{user_prompt}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.0  # Убираем креативность полностью
        )
        
        raw_content = response.choices[0].message.content
        clean_content = clean_json_string(raw_content)
        
        return response_model.model_validate_json(clean_content)
        
    except Exception as e:
        raw_info = raw_content if 'raw_content' in locals() else 'Нет ответа'
        logger.error(f"Ошибка LLM или валидации: {e}\nОтвет LLM: {raw_info}")
        raise

async def extract_profile(text: str) -> ProfileSummary:
    system = "Ты - робот-парсер резюме. Твоя задача: перевести текст резюме в структурированный JSON."
    return await get_llm_response(system, text, ProfileSummary)

async def extract_filters(text: str) -> SearchFilters:
    system = "Ты - робот-парсер требований. Твоя задача: извлечь пожелания кандидата к работе в JSON."
    return await get_llm_response(system, text, SearchFilters)

async def update_filters(current_filters: SearchFilters, update_text: str) -> SearchFilters:
    system = "Ты - робот для обновления JSON. Обнови текущие поля на основе нового текста."
    prompt = f"ТЕКУЩИЙ JSON: {current_filters.model_dump_json()}\nНОВОЕ ПОЖЕЛАНИЕ: {update_text}"
    return await get_llm_response(system, prompt, SearchFilters)

async def analyze_vacancy(post_text: str, profile_summary: str, filters_summary: str) -> VacancyAnalysisResult:
    system = (
        "Ты - робот-рекрутер. Сравни вакансию с профилем кандидата. "
        "Дай оценку match_score (0-100) и краткую причину match_reason."
    )
    prompt = f"ПРОФИЛЬ: {profile_summary}\nФИЛЬТРЫ: {filters_summary}\nВАКАНСИЯ: {post_text}"
    return await get_llm_response(system, prompt, VacancyAnalysisResult)
