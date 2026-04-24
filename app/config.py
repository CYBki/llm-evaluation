from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RAG Eval API"
    database_url: str  # REQUIRED — no default, must be set via env/`.env`
    # ── Chat LLM (OpenAI-compatible endpoint: OpenAI / OpenRouter / Azure / vLLM) ─
    # Backward-compat: OPENAI_API_KEY / OPENAI_BASE_URL env names still work.
    llm_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_API_KEY", "OPENAI_API_KEY"),
    )
    llm_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        validation_alias=AliasChoices("LLM_BASE_URL", "OPENAI_BASE_URL"),
    )
    llm_timeout_seconds: float = Field(
        default=120.0,
        validation_alias=AliasChoices("LLM_TIMEOUT_SECONDS", "OPENAI_TIMEOUT_SECONDS"),
    )
    # Embedding endpoint (optional, falls back to llm_base_url / llm_api_key).
    # Use this when chat is routed via OpenRouter (no embeddings) but you still
    # want embeddings from OpenAI.
    embedding_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "EMBEDDING_BASE_URL", "OPENAI_EMBEDDING_BASE_URL"
        ),
    )
    embedding_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "EMBEDDING_API_KEY", "OPENAI_EMBEDDING_API_KEY"
        ),
    )
    # OpenRouter provider routing (used only when llm_base_url points at
    # openrouter.ai). Comma-separated, ordered preference list. Leave empty
    # to let OpenRouter pick any provider that supports the requested
    # parameters (controlled via openrouter_require_parameters).
    openrouter_provider_order: str = ""
    openrouter_require_parameters: bool = True
    stage_1_model: str = "gpt-5.2"
    stage_2_model: str = "gpt-4o-mini"
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

    # ── Webhook ──
    webhook_secret: str = ""  # HMAC-SHA256 signing key for webhook payloads
    webhook_timeout_seconds: float = 10.0
    webhook_max_retries: int = 3

    # ── Model pricing (per 1M tokens, USD) ──
    # Defaults target Qwen3 via OpenRouter; override per-env for other models.
    stage1_input_price: float = 0.20  # qwen3-235b-a22b input
    stage1_output_price: float = 0.60  # qwen3-235b-a22b output
    stage2_input_price: float = 0.10  # qwen3-32b input
    stage2_output_price: float = 0.30  # qwen3-32b output

    # ── Prompt truncation limits (characters) ──
    max_question_chars: int = 8_000
    max_answer_chars: int = 40_000
    max_context_total_chars: int = 80_000
    max_single_context_chars: int = 20_000
    max_ground_truth_chars: int = 10_000

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
