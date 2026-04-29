from pydantic import BaseModel, Field
from typing import Optional, List


class ProfileSummary(BaseModel):
    roles: List[str] = Field(description="Список должностей, на которые претендует кандидат")
    skills: List[str] = Field(description="Ключевые навыки кандидата (ТОЛЬКО hard skills, технологии, фреймворки, языки)")
    experience_years: Optional[float] = Field(description="Опыт работы в годах (1.5 = 1 год и 6 месяцев). Если нет данных — null.", default=None)
    summary: str = Field(description="Профессиональная сухая выжимка профиля в 2-3 предложениях (кто, стек, грейд)")


class SearchFilters(BaseModel):
    formats: List[str] = Field(description="Нормализованные форматы работы (удаленка, офис, гибрид, релокация)", default_factory=list)
    min_salary: Optional[int] = Field(description="Минимальная желаемая зарплата (ТОЛЬКО число, например 200000)", default=None)
    currency: Optional[str] = Field(description="Валюта зарплаты (RUB, USD, EUR). По умолчанию для РФ — RUB.", default=None)
    must_have_skills: List[str] = Field(description="Навыки или условия, без которых кандидат точно не рассмотрит оффер", default_factory=list)
    excluded_keywords: List[str] = Field(description="Красные флаги — слова-исключения (стартап, галера, web3, 1С, офис и т.д.)", default_factory=list)


class VacancyAnalysisResult(BaseModel):
    # --- Chain of Thought: сначала рассуждения, потом вердикт ---
    reasoning: str = Field(description="ПОДРОБНЫЙ АНАЛИЗ: шаг за шагом сравни профиль и фильтры с вакансией. Рассуждай, прежде чем ставить оценку.")
    is_vacancy: bool = Field(description="Является ли пост реальной вакансией (false для рекламы, курсов, мемов, новостей)")
    role: Optional[str] = Field(description="Должность из вакансии", default=None)
    salary: Optional[str] = Field(description="Вилка или сумма зарплаты из текста вакансии", default=None)
    format: Optional[str] = Field(description="Формат работы (офис, удаленка, гибрид)", default=None)
    match_score: Optional[int] = Field(ge=0, le=100, description="Итоговая оценка от 0 до 100 на основе рассуждений в reasoning.", default=None)
    match_reason: Optional[str] = Field(description="КРАТКАЯ выжимка для пользователя (1-2 предложения), почему вакансия подходит или нет.", default=None)
