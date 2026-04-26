import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    bot_token: str = Field(..., env='BOT_TOKEN')
    admin_tg_id: int = Field(..., env='ADMIN_TG_ID')
    
    llm_api_key: str = Field(..., env='LLM_API_KEY')
    llm_base_url: str = Field("https://openrouter.ai/api/v1", env='LLM_BASE_URL')
    llm_model: str = Field("openai:gpt-4o-mini", env='LLM_MODEL')

    db_path: str = Field("sqlite+aiosqlite:///database.db", env='DB_PATH')

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

config = Settings()
