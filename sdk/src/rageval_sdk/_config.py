"""
Evaluation configuration.

Replaces the server-side Settings class with a simple dataclass
that users can customise when calling evaluate().
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvalConfig:
    """Configuration for standalone RAG evaluation.

    Args:
        api_key: Your OpenAI (or compatible) API key. **Required.**
        base_url: LLM API base URL.
        stage_1_model: Model for Stage 1 rubric reasoning.
        stage_2_model: Model for Stage 2 JSON conversion.
        rag_metrics_model: Model for RAG metric computations.
        timeout_seconds: HTTP request timeout.
        max_question_chars: Truncation limit for question text.
        max_answer_chars: Truncation limit for answer text.
        max_context_total_chars: Total truncation budget for all contexts.
        max_single_context_chars: Truncation limit per single context.
        max_ground_truth_chars: Truncation limit for ground truth.
        stage1_input_price: Stage 1 input price per 1M tokens (USD).
        stage1_output_price: Stage 1 output price per 1M tokens (USD).
        stage2_input_price: Stage 2 input price per 1M tokens (USD).
        stage2_output_price: Stage 2 output price per 1M tokens (USD).
    """

    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    stage_1_model: str = "gpt-4o"
    stage_2_model: str = "gpt-4o-mini"
    rag_metrics_model: str = "gpt-4o-mini"
    timeout_seconds: float = 120.0

    # Prompt truncation limits (characters)
    max_question_chars: int = 8_000
    max_answer_chars: int = 40_000
    max_context_total_chars: int = 80_000
    max_single_context_chars: int = 20_000
    max_ground_truth_chars: int = 10_000

    # Model pricing (per 1M tokens, USD)
    stage1_input_price: float = 2.50
    stage1_output_price: float = 10.0
    stage2_input_price: float = 0.15
    stage2_output_price: float = 0.60

    # Versioning
    prompt_version: str = "v1.0"
    rubric_version: str = "v1.0"
    hallucination_prompt_version: str = "v1.0"

    # OpenRouter provider routing (only used when base_url contains openrouter.ai)
    openrouter_provider_order: str = ""
    openrouter_allow_fallbacks: bool = True
    openrouter_require_parameters: bool = True
