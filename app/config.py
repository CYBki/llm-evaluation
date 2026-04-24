from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RAG Eval API"
    database_url: str  # REQUIRED — no default, must be set via env/`.env`
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_timeout_seconds: float = 120.0
    # Embedding endpoint can be pinned to OpenAI even when chat uses OpenRouter
    # (OpenRouter does not offer embeddings). Defaults fall back to the
    # OpenAI-compatible endpoint above when unset.
    openai_embedding_base_url: str | None = None
    openai_embedding_api_key: str | None = None
    # OpenRouter provider routing (used only when openai_base_url points at
    # openrouter.ai). Comma-separated, ordered preference list.
    openrouter_provider_order: str = "fireworks,together,deepinfra"
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
