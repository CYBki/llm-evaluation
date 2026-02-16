from __future__ import annotations

import json
from typing import Any

from app.config import settings
from app.evaluation.llm_client import LLMClientError, OpenAILLMClient
from app.evaluation.prompts import (
    STAGE_1_SYSTEM_PROMPT,
    STAGE_2_SYSTEM_PROMPT,
    build_stage_1_user_prompt,
    build_stage_2_user_prompt,
)


async def evaluate_trace(question: str, answer: str, contexts: list[str] | None) -> dict[str, Any]:
    context_items = contexts or []
    client = OpenAILLMClient()

    if not client.is_enabled:
        return {
            "clarity": None,
            "specificity": None,
            "is_off_topic": None,
            "completeness": None,
            "coherence": None,
            "helpfulness": None,
            "is_deflection": None,
            "overall_score": None,
            "evaluation_confidence": None,
            "reasoning_summary": "OPENAI_API_KEY not configured; evaluation skipped.",
            "disagreement_claims": [],
            "stage_1_reasoning": None,
            "raw_response": {"skipped": True, "reason": "missing_openai_api_key"},
            "model_used": f"{settings.stage_1_model} + {settings.stage_2_model}",
            "prompt_version": settings.prompt_version,
            "rubric_version": settings.rubric_version,
        }

    try:
        stage_1 = await client.chat_completion(
            model=settings.stage_1_model,
            system_prompt=STAGE_1_SYSTEM_PROMPT,
            user_prompt=build_stage_1_user_prompt(question, answer, context_items),
        )

        stage_2 = await client.chat_completion(
            model=settings.stage_2_model,
            system_prompt=STAGE_2_SYSTEM_PROMPT,
            user_prompt=build_stage_2_user_prompt(stage_1.content),
        )

        parsed = _safe_parse_json(stage_2.content)

        return {
            "clarity": parsed.get("clarity"),
            "specificity": parsed.get("specificity"),
            "is_off_topic": parsed.get("is_off_topic"),
            "completeness": parsed.get("completeness"),
            "coherence": parsed.get("coherence"),
            "helpfulness": parsed.get("helpfulness"),
            "is_deflection": parsed.get("is_deflection"),
            "overall_score": parsed.get("overall_score"),
            "evaluation_confidence": parsed.get("evaluation_confidence"),
            "reasoning_summary": parsed.get("reasoning_summary"),
            "disagreement_claims": parsed.get("disagreement_claims", []),
            "stage_1_reasoning": stage_1.content,
            "raw_response": stage_2.raw,
            "model_used": f"{settings.stage_1_model} + {settings.stage_2_model}",
            "prompt_version": settings.prompt_version,
            "rubric_version": settings.rubric_version,
        }
    except LLMClientError as exc:
        return {
            "clarity": None,
            "specificity": None,
            "is_off_topic": None,
            "completeness": None,
            "coherence": None,
            "helpfulness": None,
            "is_deflection": None,
            "overall_score": None,
            "evaluation_confidence": None,
            "reasoning_summary": f"Evaluation failed: {exc}",
            "disagreement_claims": [],
            "stage_1_reasoning": None,
            "raw_response": {"failed": True, "reason": str(exc)},
            "model_used": f"{settings.stage_1_model} + {settings.stage_2_model}",
            "prompt_version": settings.prompt_version,
            "rubric_version": settings.rubric_version,
        }


def _safe_parse_json(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {
            "reasoning_summary": "Stage 2 JSON parse failed",
            "disagreement_claims": [],
        }
