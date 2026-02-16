from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RAG Eval API"
    database_url: str = "postgresql+psycopg2://postgres:postgres@db:5432/rageval"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_timeout_seconds: float = 30.0
    stage_1_model: str = "gpt-5.2"
    stage_2_model: str = "gpt-5-mini"
    prompt_version: str = "v1.0"
    rubric_version: str = "v1.0"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
