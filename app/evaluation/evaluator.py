from __future__ import annotations

import json
from typing import Any

import logging
import re

from app.config import settings
from app.evaluation.llm_client import LLMClientError, OpenAILLMClient
from app.evaluation.prompts import (
    STAGE_2_JSON_SCHEMA,
    STAGE_2_REPAIR_SYSTEM_PROMPT,
    STAGE_1_SYSTEM_PROMPT,
    STAGE_2_SYSTEM_PROMPT,
    build_stage_1_user_prompt,
    build_stage_2_repair_user_prompt,
    build_stage_2_user_prompt,
)
from app.evaluation.rag_metrics import compute_rag_metrics

logger = logging.getLogger(__name__)

_FLOAT_FIELDS = [
    "clarity",
    "completeness",
    "coherence",
    "helpfulness",
    "overall_score",
    "evaluation_confidence",
]
_BOOL_FIELDS = ["is_off_topic", "is_deflection"]
_REQUIRED_FIELDS = (
    _FLOAT_FIELDS + _BOOL_FIELDS + ["reasoning_summary", "disagreement_claims"]
)

_MAX_STAGE_2_RETRIES = 3


def _compute_cost(
    stage1_prompt_tokens: int,
    stage1_completion_tokens: int,
    stage2_prompt_tokens: int,
    stage2_completion_tokens: int,
) -> float:
    """Compute total cost in USD using actual per-stage token counts.

    Stage 1 uses gpt-5.2 pricing, Stage 2 + RAG metrics use gpt-5-mini pricing.
    """
    cost = (
        (stage1_prompt_tokens * settings.stage1_input_price / 1_000_000)
        + (stage1_completion_tokens * settings.stage1_output_price / 1_000_000)
        + (stage2_prompt_tokens * settings.stage2_input_price / 1_000_000)
        + (stage2_completion_tokens * settings.stage2_output_price / 1_000_000)
    )
    return round(cost, 6)


# ── Overall Score Weights ──────────────────────────────────────────────
# Weighted formula replaces LLM-generated overall_score for consistency.
# hallucination_score and completeness come from RAG analytical metrics.
_OVERALL_WEIGHTS = {
    "hallucination_score": 0.15,
    "faithfulness": 0.10,
    "answer_relevancy": 0.15,
    "completeness": 0.10,
    "context_precision": 0.10,
    "context_recall": 0.10,
    "helpfulness": 0.15,
    "coherence": 0.05,
    "clarity": 0.05,
    "citation_check": 0.05,
}

# When is_deflection is True, cap overall_score to this value.
# Rationale: a deflection ("I don't know" with no info) should never score high,
# even if clarity/coherence are perfect.
_DEFLECTION_SCORE_CAP = 0.20

# Off-topic answers should also never score high.
_OFF_TOPIC_SCORE_CAP = 0.20

# If any claim is explicitly contradicted by context, apply an additional cap.
_CONTRADICTION_SCORE_CAP = 0.35


def _compute_overall_score(
    parsed: dict[str, Any],
    rag_results: dict[str, Any],
    is_deflection: bool = False,
    is_off_topic: bool = False,
    has_contradiction: bool = False,
) -> float | None:
    """Compute overall_score as a weighted average of rubric + RAG metrics.

    Score caps:
    - is_deflection => _DEFLECTION_SCORE_CAP
    - is_off_topic => _OFF_TOPIC_SCORE_CAP
    - has_contradiction => _CONTRADICTION_SCORE_CAP
    """
    sources = {
        "hallucination_score": rag_results.get("hallucination_score"),
        "faithfulness": rag_results.get("faithfulness"),
        "completeness": rag_results.get("completeness"),
        "answer_relevancy": rag_results.get("answer_relevancy"),
        "context_precision": rag_results.get("context_precision"),
        "context_recall": rag_results.get("context_recall"),
        "coherence": parsed.get("coherence"),
        "helpfulness": parsed.get("helpfulness"),
        "clarity": parsed.get("clarity"),
        "citation_check": rag_results.get("citation_check"),
    }

    total_weight = 0.0
    weighted_sum = 0.0
    for key, weight in _OVERALL_WEIGHTS.items():
        val = sources.get(key)
        if val is not None:
            try:
                val = float(val)
                weighted_sum += val * weight
                total_weight += weight
            except (ValueError, TypeError):
                continue

    if total_weight == 0.0:
        # Fallback to LLM-generated score if no metrics available
        score = parsed.get("overall_score")
    else:
        score = round(weighted_sum / total_weight, 4)

    # Apply score caps
    if is_deflection and score is not None:
        score = min(score, _DEFLECTION_SCORE_CAP)
        logger.info(
            "is_deflection=True → overall_score capped at %.2f", _DEFLECTION_SCORE_CAP
        )

    if is_off_topic and score is not None:
        score = min(score, _OFF_TOPIC_SCORE_CAP)
        logger.info(
            "is_off_topic=True → overall_score capped at %.2f", _OFF_TOPIC_SCORE_CAP
        )

    if has_contradiction and score is not None:
        score = min(score, _CONTRADICTION_SCORE_CAP)
        logger.info(
            "contradicted_claim=True → overall_score capped at %.2f",
            _CONTRADICTION_SCORE_CAP,
        )

    return score


def _has_contradicted_claims(claims: list[dict[str, Any]] | None) -> bool:
    """Check hallucination_claims for confirmed contradictions."""
    if not claims:
        return False

    for claim in claims:
        if (
            isinstance(claim, dict)
            and str(claim.get("disagreement_type", "")).lower()
            == "confirmed contradiction"
        ):
            return True
    return False


def _coerce_off_topic_flag(
    llm_is_off_topic: Any,
    answer_relevancy: Any,
    helpfulness: Any,
) -> bool:
    """Derive a robust off-topic flag with a deterministic hard-override.

    Hard override (always wins):
      if answer_relevancy == 0 and helpfulness == 0 -> off-topic = True
    Otherwise trust the LLM boolean.
    """
    # ── hard override: scores prove the answer is completely irrelevant ──
    try:
        relevancy = float(answer_relevancy)
    except (TypeError, ValueError):
        relevancy = None

    try:
        help_score = float(helpfulness)
    except (TypeError, ValueError):
        help_score = None

    if relevancy == 0.0 and help_score == 0.0:
        logger.info("off-topic hard-override: answer_relevancy=0 and helpfulness=0")
        return True

    # ── trust LLM flag when scores don't trigger override ──
    if isinstance(llm_is_off_topic, bool):
        return llm_is_off_topic

    return False


async def evaluate_trace(
    question: str,
    answer: str,
    contexts: list[str] | None,
    ground_truth: str | None = None,
) -> dict[str, Any]:
    context_items = contexts or []
    client = OpenAILLMClient()

    if not client.is_enabled:
        return {
            "clarity": None,
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
            "answer_relevancy": None,
            "faithfulness": None,
            "hallucination_score": None,
            "citation_check": None,
            "hallucination_claims": [],
            "completeness_key_points": [],
            "context_precision": None,
            "context_recall": None,
        }

    try:
        import asyncio
        import time as _time

        _t0 = _time.perf_counter()

        # Run Stage 1 (rubric CoT) and RAG metrics concurrently
        stage_1_task = asyncio.create_task(
            client.chat_completion(
                model=settings.stage_1_model,
                system_prompt=STAGE_1_SYSTEM_PROMPT,
                user_prompt=build_stage_1_user_prompt(question, answer, context_items),
                max_completion_tokens=4096,
            )
        )
        rag_metrics_task = asyncio.create_task(
            compute_rag_metrics(question, answer, contexts, ground_truth)
        )

        stage_1 = await stage_1_task
        _t1 = _time.perf_counter()
        rag_results = await rag_metrics_task
        _t2 = _time.perf_counter()

        logger.info(
            "Timing — Stage 1: %.1fs | RAG metrics: %.1fs (parallel block: %.1fs)",
            _t1 - _t0, _t2 - _t0, _t2 - _t0,
        )

        # ── Token accumulator (per-stage for accurate cost) ──
        stage1_prompt_tokens = stage_1.prompt_tokens
        stage1_completion_tokens = stage_1.completion_tokens

        # Stage 2 + RAG metrics both use gpt-5-mini
        stage2_prompt_tokens = rag_results.get("_prompt_tokens", 0)
        stage2_completion_tokens = rag_results.get("_completion_tokens", 0)

        # ── Stage 2: structured output with retry loop ──
        parsed: dict[str, Any] = {}
        raw_responses: list[dict[str, Any]] = []
        last_output = ""

        for attempt in range(_MAX_STAGE_2_RETRIES):
            if attempt == 0:
                s2_resp = await client.chat_completion(
                    model=settings.stage_2_model,
                    system_prompt=STAGE_2_SYSTEM_PROMPT,
                    user_prompt=build_stage_2_user_prompt(stage_1.content),
                    max_completion_tokens=4096,
                    json_schema=STAGE_2_JSON_SCHEMA,
                )
            else:
                validation_errors = _describe_validation_errors(parsed)
                logger.info(
                    "Stage 2 retry %d/%d – errors: %s",
                    attempt + 1,
                    _MAX_STAGE_2_RETRIES,
                    validation_errors,
                )
                s2_resp = await client.chat_completion(
                    model=settings.stage_2_model,
                    system_prompt=STAGE_2_REPAIR_SYSTEM_PROMPT,
                    user_prompt=build_stage_2_repair_user_prompt(
                        last_output, stage_1.content, validation_errors
                    ),
                    max_completion_tokens=4096,
                    json_schema=STAGE_2_JSON_SCHEMA,
                )

            last_output = s2_resp.content
            raw_responses.append(s2_resp.raw)
            parsed = _safe_parse_json(s2_resp.content)

            # Accumulate Stage 2 tokens (same pricing tier as RAG metrics)
            stage2_prompt_tokens += s2_resp.prompt_tokens
            stage2_completion_tokens += s2_resp.completion_tokens

            errors = _validate_schema(parsed)
            if not errors:
                logger.info("Stage 2 succeeded on attempt %d", attempt + 1)
                break
        else:
            # All LLM retries exhausted – try deterministic regex fallback
            logger.warning("Stage 2 LLM retries exhausted, trying regex fallback")
            fallback = _regex_extract_scores(stage_1.content)
            if fallback.get("overall_score") is not None:
                parsed = fallback

        _t3 = _time.perf_counter()
        logger.info(
            "Timing — Stage 2: %.1fs | Total: %.1fs",
            _t3 - _t2, _t3 - _t0,
        )

        is_off_topic_value = _coerce_off_topic_flag(
            parsed.get("is_off_topic"),
            rag_results.get("answer_relevancy"),
            parsed.get("helpfulness"),
        )

        return {
            "clarity": parsed.get("clarity"),
            "is_off_topic": is_off_topic_value,
            "completeness": rag_results.get("completeness"),
            "coherence": parsed.get("coherence"),
            "helpfulness": parsed.get("helpfulness"),
            "is_deflection": parsed.get("is_deflection"),
            "overall_score": _compute_overall_score(
                parsed,
                rag_results,
                is_deflection=bool(parsed.get("is_deflection")),
                is_off_topic=is_off_topic_value,
                has_contradiction=_has_contradicted_claims(
                    rag_results.get("hallucination_claims")
                ),
            ),
            "evaluation_confidence": parsed.get("evaluation_confidence"),
            "reasoning_summary": parsed.get("reasoning_summary"),
            "disagreement_claims": parsed.get("disagreement_claims", []),
            "stage_1_reasoning": stage_1.content,
            "raw_response": raw_responses,
            "model_used": f"{settings.stage_1_model} + {settings.stage_2_model}",
            "prompt_version": settings.prompt_version,
            "rubric_version": settings.rubric_version,
            "answer_relevancy": rag_results.get("answer_relevancy"),
            "faithfulness": rag_results.get("faithfulness"),
            "hallucination_score": rag_results.get("hallucination_score"),
            "citation_check": rag_results.get("citation_check"),
            "hallucination_claims": rag_results.get("hallucination_claims", []),
            "completeness_key_points": rag_results.get("completeness_key_points", []),
            "context_precision": rag_results.get("context_precision"),
            "context_recall": rag_results.get("context_recall"),
            # Token usage & cost (per-stage for accurate pricing)
            "prompt_tokens": stage1_prompt_tokens + stage2_prompt_tokens,
            "completion_tokens": stage1_completion_tokens + stage2_completion_tokens,
            "total_tokens": (
                stage1_prompt_tokens
                + stage2_prompt_tokens
                + stage1_completion_tokens
                + stage2_completion_tokens
            ),
            "cost_usd": _compute_cost(
                stage1_prompt_tokens,
                stage1_completion_tokens,
                stage2_prompt_tokens,
                stage2_completion_tokens,
            ),
        }
    except LLMClientError as exc:
        return {
            "clarity": None,
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
            "answer_relevancy": None,
            "faithfulness": None,
            "hallucination_score": None,
            "citation_check": None,
            "hallucination_claims": [],
            "completeness_key_points": [],
            "context_precision": None,
            "context_recall": None,
        }


def _safe_parse_json(content: str) -> dict[str, Any]:
    """Best-effort extraction of a JSON object from model output."""
    raw = (content or "").strip()
    candidates: list[str] = [raw]

    # Strip markdown code fences
    if raw.startswith("```"):
        lines = raw.splitlines()
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            body = "\n".join(lines[1:-1]).strip()
            if body:
                candidates.insert(0, body)

    # Extract outermost { ... }
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.insert(0, raw[start : end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return _coerce_types(parsed)

    return {
        "reasoning_summary": "Stage 2 JSON parse failed",
        "disagreement_claims": [],
    }


def _coerce_types(parsed: dict[str, Any]) -> dict[str, Any]:
    """Clamp floats to [0,1] and coerce string booleans."""
    for field in _FLOAT_FIELDS:
        val = parsed.get(field)
        if val is not None:
            try:
                val = float(val)
                parsed[field] = max(0.0, min(1.0, val))
            except (ValueError, TypeError):
                parsed[field] = None
    for field in _BOOL_FIELDS:
        val = parsed.get(field)
        if isinstance(val, str):
            parsed[field] = val.lower() in ("true", "1", "yes", "evet")
    if not isinstance(parsed.get("disagreement_claims"), list):
        parsed["disagreement_claims"] = []
    return parsed


def _validate_schema(parsed: dict[str, Any]) -> list[str]:
    """Return list of validation error descriptions.  Empty = valid."""
    errors: list[str] = []
    for f in _REQUIRED_FIELDS:
        if f not in parsed or parsed[f] is None:
            errors.append(f"Missing or null field: {f}")
    for f in _FLOAT_FIELDS:
        v = parsed.get(f)
        if v is not None and not isinstance(v, (int, float)):
            errors.append(f"{f} must be a number, got {type(v).__name__}")
    for f in _BOOL_FIELDS:
        v = parsed.get(f)
        if v is not None and not isinstance(v, bool):
            errors.append(f"{f} must be boolean, got {type(v).__name__}")
    if not isinstance(parsed.get("disagreement_claims"), list):
        errors.append("disagreement_claims must be an array")
    if (parsed.get("reasoning_summary") or "").strip() == "Stage 2 JSON parse failed":
        errors.append("JSON parse failed")
    return errors


def _describe_validation_errors(parsed: dict[str, Any]) -> str:
    """Human-readable validation error string for retry prompt."""
    errors = _validate_schema(parsed)
    return "; ".join(errors) if errors else "unknown"


def _regex_extract_scores(stage_1_text: str) -> dict[str, Any]:
    """Deterministic fallback: extract scores from Stage 1 CoT text via regex."""
    result: dict[str, Any] = {
        "reasoning_summary": "Scores extracted via regex fallback from Stage 1 text.",
        "disagreement_claims": [],
    }

    # Patterns like "CLARITY: 0.7", "Clarity: 0.7/1.0", "clarity = 0.7" etc.
    float_patterns = {
        "clarity": r"(?:CLARITY|clarity)[:\s=]+([01](?:\.\d+)?)",
        "completeness": r"(?:COMPLETENESS|completeness)[:\s=]+([01](?:\.\d+)?)",
        "coherence": r"(?:COHERENCE|coherence)[:\s=]+([01](?:\.\d+)?)",
        "helpfulness": r"(?:HELPFULNESS|helpfulness)[:\s=]+([01](?:\.\d+)?)",
        "evaluation_confidence": r"(?:EVALUATION.?CONFIDENCE|confidence)[:\s=]+([01](?:\.\d+)?)",
    }

    for field, pattern in float_patterns.items():
        m = re.search(pattern, stage_1_text, re.IGNORECASE)
        if m:
            try:
                result[field] = max(0.0, min(1.0, float(m.group(1))))
            except ValueError:
                pass

    # Booleans
    off_topic_m = re.search(
        r"(?:IS.?OFF.?TOPIC|off.?topic)[:\s=]+(true|false|evet|hayir)",
        stage_1_text,
        re.IGNORECASE,
    )
    if off_topic_m:
        result["is_off_topic"] = off_topic_m.group(1).lower() in ("true", "evet")

    defl_m = re.search(
        r"(?:IS.?DEFLECTION|deflection)[:\s=]+(true|false|evet|hayir)",
        stage_1_text,
        re.IGNORECASE,
    )
    if defl_m:
        result["is_deflection"] = defl_m.group(1).lower() in ("true", "evet")

    # Compute overall_score as average of found float scores
    found_scores = [
        v
        for k, v in result.items()
        if k in _FLOAT_FIELDS and isinstance(v, (int, float))
    ]
    if found_scores:
        result["overall_score"] = round(sum(found_scores) / len(found_scores), 2)
        result["evaluation_confidence"] = result.get(
            "evaluation_confidence", round(len(found_scores) / len(_FLOAT_FIELDS), 2)
        )

    return result
