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
    
    logger.info("Request Start: Sending request to LLM.")
    logger.debug(f"System Prompt:\n{full_system_prompt}")
    logger.debug(f"User Prompt:\n{user_prompt}")
    
    start_time = asyncio.get_event_loop().time()
    
    try:
        response = await client.chat.completions.create(
            model=config.llm_model,
            messages=[
                {"role": "system", "content": full_system_prompt},
                {"role": "user", "content": f"ОБРАБОТАЙ ЭТОТ ТЕКСТ И ВЫДАЙ JSON: \n\n{user_prompt}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.0  # Детерминированность — никакой креативности
        )
        
        latency = asyncio.get_event_loop().time() - start_time
        logger.info(f"Response received. Latency: {latency:.2f}s")
        
        raw_content = response.choices[0].message.content
        logger.debug(f"Raw Response:\n{raw_content}")
        
        clean_content = clean_json_string(raw_content)
        
        try:
            return response_model.model_validate_json(clean_content)
        except Exception as validation_error:
            # specifically for pydantic ValidationError or json decode errors
            logger.error(f"Validation Error: {validation_error}\nRaw Content:\n{clean_content}")
            raise
            
    except Exception as e:
        raw_info = raw_content if 'raw_content' in locals() else 'Нет ответа'
        logger.error(f"Ошибка LLM или валидации: {e}\nОтвет LLM: {raw_info}")
        raise

async def extract_profile(text: str) -> ProfileSummary:
    system = """Ты — Senior IT Recruiter AI. 
Твоя задача: извлечь структурированные факты из неструктурированного текста резюме кандидата.

ПРАВИЛА ИЗВЛЕЧЕНИЯ:
1. roles: Определи конкретные должности (например, Backend Developer, Data Scientist, QA Engineer). Если не указано явно, сделай вывод из навыков.
2. skills: Извлекай ТОЛЬКО hard skills, технологии, языки программирования, фреймворки и инструменты. Игнорируй soft skills (коммуникабельность, стрессоустойчивость и т.д.).
3. experience_years: Посчитай общий релевантный опыт в годах (например, 1 год и 6 месяцев = 1.5). Если точных дат нет, оцени примерно по тексту. Если опыта нет, верни null.
4. summary: Сделай профессиональную, сухую выжимку профиля в 2-3 предложениях (кто это, какой основной стек, грейд)."""
    return await get_llm_response(system, text, ProfileSummary)

async def extract_filters(text: str) -> SearchFilters:
    system = """Ты — IT Career Consultant AI. 
Твоя задача: извлечь пожелания кандидата к будущей работе из текста.

ПРАВИЛА ИЗВЛЕЧЕНИЯ:
1. formats: Нормализуй форматы до стандартных (удаленка, офис, гибрид, релокация). Пойми синонимы (например, "из дома" -> "удаленка").
2. min_salary: Найди минимально желаемую сумму. Верни ТОЛЬКО число (например, 200000).
3. currency: Определи валюту (RUB, USD, EUR). По умолчанию, если контекст РФ, ставь RUB.
4. must_have_skills: Навыки или условия, без которых кандидат точно не будет рассматривать оффер.
5. excluded_keywords: Красные флаги кандидата (например: "стартап", "галера", "web3", "1С", "офис")."""
    return await get_llm_response(system, text, SearchFilters)

async def update_filters(current_filters: SearchFilters, update_text: str) -> SearchFilters:
    system = """Ты — AI Data State Manager. 
Твоя задача: обновить существующий JSON объект с фильтрами поиска на основе нового текстового запроса от пользователя.

ПРАВИЛА ОБНОВЛЕНИЯ:
1. Внимательно проанализируй ТЕКУЩИЙ JSON.
2. Пойми намерение пользователя (добавить, удалить, изменить).
3. Сохрани все существующие поля ТЕКУЩЕГО JSON, если пользователь явно не попросил их удалить или изменить.
4. Если пользователь пишет "добавь удаленку", добавь "удаленка" в массив formats, не удаляя остальные форматы.
5. Если пользователь пишет "зп от 300к", обнови min_salary на 300000."""
    prompt = f"ТЕКУЩИЙ JSON: {current_filters.model_dump_json()}\nНОВОЕ ПОЖЕЛАНИЕ: {update_text}"
    return await get_llm_response(system, prompt, SearchFilters)

async def analyze_vacancy(post_text: str, profile_summary: str, filters_summary: str) -> VacancyAnalysisResult:
    system = """Ты — Expert Technical Recruiter AI. 
Твоя задача: проанализировать пост из Telegram-канала, определить, является ли он вакансией, и оценить, насколько он подходит кандидату на основе его ПРОФИЛЯ и ФИЛЬТРОВ.

АЛГОРИТМ РАБОТЫ И РУБРИКАТОР ОЦЕНКИ (match_score от 0 до 100):
Шаг 1. Проверка на спам (is_vacancy): Если это реклама курсов, мем, новость или поиск исполнителя на разовый фриланс-проект — ставь is_vacancy=false и match_score=0.
Шаг 2. Проверка красных флагов (excluded_keywords): Если в вакансии явно присутствуют слова из excluded_keywords кандидата — ставь match_score от 0 до 20.
Шаг 3. Базовая оценка: Изначально вакансия имеет 100 баллов.
Шаг 4. Штрафы (вычитай из 100):
   - Формат работы: Если кандидат хочет ТОЛЬКО удаленку, а вакансия ТОЛЬКО офис — штраф -50 баллов.
   - Зарплата: Если ЗП указана и она НИЖЕ min_salary кандидата более чем на 15% — штраф -40 баллов. ВАЖНО: Если ЗП в вакансии НЕ УКАЗАНА (что часто бывает в IT), НЕ ШТРАФУЙ за это вообще.
   - Стек технологий: За каждую критичную несовпадающую технологию (особенно из must_have_skills) — штраф -15 баллов.
   - Опыт: Если вакансия Senior (требует 5+ лет), а у кандидата 1 год — штраф -40 баллов.

ВАЖНОЕ ЗАМЕЧАНИЕ: Вакансии в IT часто описаны неформально. Если суть вакансии подходит под профиль, будь снисходителен к отсутствию формальных ключевых слов.

ТРЕБОВАНИЯ К ЗАПОЛНЕНИЮ JSON:
1. Сначала ОБЯЗАТЕЛЬНО заполни поле "reasoning". В нем текстом опиши свои рассуждения по каждому шагу алгоритма выше.
2. Только после написания "reasoning", выведи финальный "match_score" (целое число).
3. Поле "match_reason" сделай очень коротким (1-2 предложения), это увидит пользователь в Telegram."""
    prompt = f"ПРОФИЛЬ: {profile_summary}\nФИЛЬТРЫ: {filters_summary}\nВАКАНСИЯ: {post_text}"
    result = await analyze_vacancy_llm(system, prompt)
    # Логируем reasoning для отладки (не попадает в Telegram, только в лог)
    logger.info(f"LLM Reasoning для вакансии: {result.reasoning[:300]}...")
    return result


async def analyze_vacancy_llm(system_prompt: str, user_prompt: str) -> VacancyAnalysisResult:
    """Выделенная функция для анализа вакансий — логирует reasoning."""
    return await get_llm_response(system_prompt, user_prompt, VacancyAnalysisResult)
