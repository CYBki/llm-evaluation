from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RAG Eval API"
    database_url: str = "postgresql+psycopg2://postgres:postgres@db:5432/rageval"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_timeout_seconds: float = 120.0
    stage_1_model: str = "gpt-5.2"
    stage_2_model: str = "gpt-5-mini"
    rag_metrics_model: str = "gpt-5-mini"
    prompt_version: str = "v1.0"
    rubric_version: str = "v1.0"
    hallucination_prompt_version: str = "v1.0"
    evaluation_mode: str = "sync"  # sync | async
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    # ── CORS ──
    cors_origins: str = ""  # comma-separated origins, e.g. "https://app.example.com,https://admin.example.com"

    # ── Prompt truncation limits (characters) ──
    max_question_chars: int = 8_000
    max_answer_chars: int = 40_000
    max_context_total_chars: int = 80_000
    max_single_context_chars: int = 20_000
    max_ground_truth_chars: int = 10_000

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
