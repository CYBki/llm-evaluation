from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RAG Eval API"
    database_url: str = "postgresql+psycopg2://postgres:postgres@db:5432/rageval"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
