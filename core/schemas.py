from pydantic import BaseModel, Field
from typing import Optional, List

class ProfileSummary(BaseModel):
    roles: List[str] = Field(description="Список должностей, на которые претендует кандидат")
    skills: List[str] = Field(description="Ключевые навыки кандидата")
    experience_years: Optional[float] = Field(description="Опыт работы в годах", default=None)
    summary: str = Field(description="Краткая выжимка (описание) кандидата")

class SearchFilters(BaseModel):
    formats: List[str] = Field(description="Форматы работы (удаленка, офис, гибрид и т.д.)", default_factory=list)
    min_salary: Optional[int] = Field(description="Минимальная зарплата (только число)", default=None)
    currency: Optional[str] = Field(description="Валюта зарплаты (USD, RUB, EUR и т.д.)", default=None)
    must_have_skills: List[str] = Field(description="Обязательные навыки (если указаны)", default_factory=list)
    excluded_keywords: List[str] = Field(description="Исключаемые слова (например: стартап, галера)", default_factory=list)

class VacancyAnalysisResult(BaseModel):
    is_vacancy: bool = Field(description="Является ли пост реальной вакансией (false для рекламы, мемов, новостей)")
    role: Optional[str] = Field(description="Должность из вакансии")
    salary: Optional[str] = Field(description="Вилка или сумма зарплаты")
    format: Optional[str] = Field(description="Формат работы")
    match_score: Optional[int] = Field(ge=0, le=100, description="Оценка от 0 до 100 насколько вакансия подходит профилю и фильтрам. Если зарплата не указана, но стек подходит, не занижать скор!")
    match_reason: Optional[str] = Field(description="Почему эта вакансия подходит или не подходит (кратко на русском)")
