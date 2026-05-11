"""
Core evaluation engine — standalone version.

Provides evaluate_trace() (async) and evaluate() (sync wrapper).
No server dependencies — runs locally with user's own API key.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from typing import Any

from rageval_sdk._config import EvalConfig
from rageval_sdk._json_utils import safe_parse_json_object
from rageval_sdk._llm_client import LLMClientError, OpenAILLMClient
from rageval_sdk._prompts import (
    STAGE_2_JSON_SCHEMA,
    STAGE_2_REPAIR_SYSTEM_PROMPT,
    STAGE_1_SYSTEM_PROMPT,
    STAGE_2_SYSTEM_PROMPT,
    build_stage_1_user_prompt,
    build_stage_2_repair_user_prompt,
    build_stage_2_user_prompt,
)
from rageval_sdk._rag_metrics import compute_rag_metrics

logger = logging.getLogger(__name__)

_FLOAT_FIELDS = [
    "clarity",
    "coherence",
    "helpfulness",
    "overall_score",
    "evaluation_confidence",
]
_BOOL_FIELDS = ["is_off_topic", "is_deflection"]
_REQUIRED_FIELDS = _FLOAT_FIELDS + _BOOL_FIELDS + ["reasoning_summary"]

_MAX_STAGE_2_RETRIES = 3

# ── Overall Score Weights ─────────────────────────────────────────────
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

_DEFLECTION_SCORE_CAP = 0.20
_OFF_TOPIC_SCORE_CAP = 0.20
_CONTRADICTION_SCORE_CAP = 0.35


def _build_empty_result(
    *,
    reasoning_summary: str,
    raw_response: dict[str, Any],
    config: EvalConfig,
) -> dict[str, Any]:
    return {
        "clarity": None,
        "is_off_topic": None,
        "completeness": None,
        "coherence": None,
        "helpfulness": None,
        "is_deflection": None,
        "overall_score": None,
        "evaluation_confidence": None,
        "reasoning_summary": reasoning_summary,
        "disagreement_claims": [],
        "stage_1_reasoning": None,
        "raw_response": raw_response,
        "model_used": f"{config.stage_1_model} + {config.stage_2_model}",
        "prompt_version": config.prompt_version,
        "rubric_version": config.rubric_version,
        "answer_relevancy": None,
        "faithfulness": None,
        "hallucination_score": None,
        "citation_check": None,
        "hallucination_claims": [],
        "completeness_key_points": [],
        "context_precision": None,
        "context_recall": None,
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
        "cost_usd": None,
    }


async def _run_stage_1(
    client: OpenAILLMClient,
    question: str,
    answer: str,
    context_items: list[str],
    config: EvalConfig,
):
    return await client.chat_completion(
        model=config.stage_1_model,
        system_prompt=STAGE_1_SYSTEM_PROMPT,
        user_prompt=build_stage_1_user_prompt(question, answer, context_items, config),
        max_completion_tokens=4096,
    )


async def _run_stage_2_with_retries(
    client: OpenAILLMClient,
    stage_1_content: str,
    config: EvalConfig,
) -> tuple[dict[str, Any], list[dict[str, Any]], int, int]:
    stage2_prompt_tokens = 0
    stage2_completion_tokens = 0
    parsed: dict[str, Any] = {}
    raw_responses: list[dict[str, Any]] = []
    last_output = ""

    for attempt in range(_MAX_STAGE_2_RETRIES):
        if attempt == 0:
            s2_resp = await client.chat_completion(
                model=config.stage_2_model,
                system_prompt=STAGE_2_SYSTEM_PROMPT,
                user_prompt=build_stage_2_user_prompt(stage_1_content),
                max_completion_tokens=2048,
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
                model=config.stage_2_model,
                system_prompt=STAGE_2_REPAIR_SYSTEM_PROMPT,
                user_prompt=build_stage_2_repair_user_prompt(
                    last_output,
                    stage_1_content,
                    validation_errors,
                ),
                max_completion_tokens=2048,
                json_schema=STAGE_2_JSON_SCHEMA,
            )

        last_output = s2_resp.content
        raw_responses.append(s2_resp.raw)
        parsed = _safe_parse_json(s2_resp.content)
        stage2_prompt_tokens += s2_resp.prompt_tokens
        stage2_completion_tokens += s2_resp.completion_tokens

        if not _validate_schema(parsed):
            logger.info("Stage 2 succeeded on attempt %d", attempt + 1)
            break
    else:
        logger.warning("Stage 2 LLM retries exhausted, trying regex fallback")
        fallback = _regex_extract_scores(stage_1_content)
        if fallback.get("overall_score") is not None:
            parsed = fallback

    return parsed, raw_responses, stage2_prompt_tokens, stage2_completion_tokens


def _build_success_result(
    *,
    parsed: dict[str, Any],
    rag_results: dict[str, Any],
    stage_1_content: str,
    raw_responses: list[dict[str, Any]],
    stage1_prompt_tokens: int,
    stage1_completion_tokens: int,
    stage2_prompt_tokens: int,
    stage2_completion_tokens: int,
    config: EvalConfig,
) -> dict[str, Any]:
    is_off_topic_value = _coerce_off_topic_flag(
        parsed.get("is_off_topic"),
        rag_results.get("answer_relevancy"),
        parsed.get("helpfulness"),
    )
    prompt_tokens = stage1_prompt_tokens + stage2_prompt_tokens
    completion_tokens = stage1_completion_tokens + stage2_completion_tokens

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
        "disagreement_claims": rag_results.get("hallucination_claims", []),
        "stage_1_reasoning": stage_1_content,
        "raw_response": raw_responses,
        "model_used": f"{config.stage_1_model} + {config.stage_2_model}",
        "prompt_version": config.prompt_version,
        "rubric_version": config.rubric_version,
        "answer_relevancy": rag_results.get("answer_relevancy"),
        "faithfulness": rag_results.get("faithfulness"),
        "hallucination_score": rag_results.get("hallucination_score"),
        "citation_check": rag_results.get("citation_check"),
        "hallucination_claims": rag_results.get("hallucination_claims", []),
        "completeness_key_points": rag_results.get("completeness_key_points", []),
        "context_precision": rag_results.get("context_precision"),
        "context_recall": rag_results.get("context_recall"),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cost_usd": _compute_cost(
            stage1_prompt_tokens,
            stage1_completion_tokens,
            stage2_prompt_tokens,
            stage2_completion_tokens,
            config,
        ),
    }


def _compute_cost(
    stage1_prompt_tokens: int,
    stage1_completion_tokens: int,
    stage2_prompt_tokens: int,
    stage2_completion_tokens: int,
    config: EvalConfig,
) -> float:
    cost = (
        (stage1_prompt_tokens * config.stage1_input_price / 1_000_000)
        + (stage1_completion_tokens * config.stage1_output_price / 1_000_000)
        + (stage2_prompt_tokens * config.stage2_input_price / 1_000_000)
        + (stage2_completion_tokens * config.stage2_output_price / 1_000_000)
    )
    return round(cost, 6)


def _compute_overall_score(
    parsed: dict[str, Any],
    rag_results: dict[str, Any],
    is_deflection: bool = False,
    is_off_topic: bool = False,
    has_contradiction: bool = False,
) -> float | None:
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
        score = parsed.get("overall_score")
    else:
        score = round(weighted_sum / total_weight, 4)

    if is_deflection and score is not None:
        score = min(score, _DEFLECTION_SCORE_CAP)

    if is_off_topic and score is not None:
        score = min(score, _OFF_TOPIC_SCORE_CAP)

    if has_contradiction and score is not None:
        score = min(score, _CONTRADICTION_SCORE_CAP)

    return score


def _has_contradicted_claims(claims: list[dict[str, Any]] | None) -> bool:
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
    try:
        relevancy = float(answer_relevancy)
    except (TypeError, ValueError):
        relevancy = None

    try:
        help_score = float(helpfulness)
    except (TypeError, ValueError):
        help_score = None

    if relevancy == 0.0 and help_score == 0.0:
        return True

    if isinstance(llm_is_off_topic, bool):
        return llm_is_off_topic

    return False


async def evaluate_trace(
    question: str,
    answer: str,
    contexts: list[str] | None = None,
    ground_truth: str | None = None,
    *,
    config: EvalConfig,
) -> dict[str, Any]:
    """Run full evaluation pipeline (Stage 1 + Stage 2 + RAG metrics).

    Args:
        question: The user question.
        answer: The LLM-generated answer.
        contexts: Retrieved context passages (for RAG evaluation).
        ground_truth: Expected correct answer (optional).
        config: Evaluation configuration (must include api_key).

    Returns:
        Dict with all evaluation metrics and scores.
    """
    context_items = contexts or []
    client = OpenAILLMClient(config)

    if not client.is_enabled:
        return _build_empty_result(
            reasoning_summary="API key not configured; evaluation skipped.",
            raw_response={"skipped": True, "reason": "missing_api_key"},
            config=config,
        )

    try:
        t0 = time.perf_counter()

        # ── Parallel pipeline: Stage 1→2 chain runs alongside RAG metrics ──
        stage_1_task = asyncio.create_task(
            _run_stage_1(client, question, answer, context_items, config)
        )
        rag_client = OpenAILLMClient(config)
        rag_metrics_task = asyncio.create_task(
            compute_rag_metrics(
                question,
                answer,
                contexts,
                ground_truth,
                client=rag_client,
                config=config,
            )
        )

        stage_1 = await stage_1_task
        t1 = time.perf_counter()
        logger.info("Timing — Stage 1: %.1fs", t1 - t0)

        stage1_prompt_tokens = stage_1.prompt_tokens
        stage1_completion_tokens = stage_1.completion_tokens

        (
            parsed,
            raw_responses,
            stage2_prompt_tokens,
            stage2_completion_tokens,
        ) = await _run_stage_2_with_retries(client, stage_1.content, config)

        t2 = time.perf_counter()
        logger.info("Timing — Stage 2: %.1fs", t2 - t1)

        rag_results = await rag_metrics_task
        t3 = time.perf_counter()

        stage2_prompt_tokens += rag_results.get("_prompt_tokens", 0)
        stage2_completion_tokens += rag_results.get("_completion_tokens", 0)

        logger.info(
            "Timing — RAG metrics: %.1fs | Pipeline total: %.1fs",
            t3 - t0,
            t3 - t0,
        )
        return _build_success_result(
            parsed=parsed,
            rag_results=rag_results,
            stage_1_content=stage_1.content,
            raw_responses=raw_responses,
            stage1_prompt_tokens=stage1_prompt_tokens,
            stage1_completion_tokens=stage1_completion_tokens,
            stage2_prompt_tokens=stage2_prompt_tokens,
            stage2_completion_tokens=stage2_completion_tokens,
            config=config,
        )
    except LLMClientError as exc:
        return _build_empty_result(
            reasoning_summary=f"Evaluation failed: {exc}",
            raw_response={"failed": True, "reason": str(exc)},
            config=config,
        )


def _resolve_config(
    api_key: str | None = None,
    config: EvalConfig | None = None,
    **overrides: Any,
) -> EvalConfig:
    """Resolve config: explicit > env var > error."""
    if config is not None:
        if api_key and not config.api_key:
            config.api_key = api_key
        return config
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ValueError(
            "API key required. Either:\n"
            "  1. Set OPENAI_API_KEY environment variable\n"
            "  2. Pass api_key='sk-...' argument\n"
            "  3. Pass config=EvalConfig(api_key='sk-...')"
        )
    return EvalConfig(api_key=key, **overrides)


def evaluate(
    question: str,
    answer: str,
    contexts: list[str] | None = None,
    ground_truth: str | None = None,
    *,
    api_key: str | None = None,
    config: EvalConfig | None = None,
    **config_overrides: Any,
) -> dict[str, Any]:
    """Evaluate a single trace (synchronous).

    Usage (3 lines):
        from rageval_sdk import evaluate
        result = evaluate("What is X?", "X is Y.", ["Context about X."])
        print(result["overall_score"])

    API key is auto-detected from OPENAI_API_KEY env var.
    """
    cfg = _resolve_config(api_key=api_key, config=config, **config_overrides)
    return asyncio.run(
        evaluate_trace(
            question=question,
            answer=answer,
            contexts=contexts,
            ground_truth=ground_truth,
            config=cfg,
        )
    )


def evaluate_batch(
    traces: list[dict[str, Any]],
    *,
    api_key: str | None = None,
    config: EvalConfig | None = None,
    max_concurrency: int = 4,
    **config_overrides: Any,
) -> list[dict[str, Any]]:
    """Evaluate multiple traces in parallel (synchronous).

    Usage:
        from rageval_sdk import evaluate_batch
        results = evaluate_batch([
            {"question": "Q1", "answer": "A1", "contexts": ["C1"]},
            {"question": "Q2", "answer": "A2", "contexts": ["C2"]},
        ])
    """
    cfg = _resolve_config(api_key=api_key, config=config, **config_overrides)

    async def _run_batch() -> list[dict[str, Any]]:
        sem = asyncio.Semaphore(max_concurrency)

        async def _eval_one(trace: dict[str, Any]) -> dict[str, Any]:
            async with sem:
                return await evaluate_trace(
                    question=trace["question"],
                    answer=trace["answer"],
                    contexts=trace.get("contexts"),
                    ground_truth=trace.get("ground_truth"),
                    config=cfg,
                )

        return await asyncio.gather(*[_eval_one(t) for t in traces])

    return asyncio.run(_run_batch())


# ── Internal helpers ─────────────────────────────────────────────────


def _safe_parse_json(content: str) -> dict[str, Any]:
    return safe_parse_json_object(
        content,
        transform=_coerce_types,
        fallback={"reasoning_summary": "Stage 2 JSON parse failed"},
    )


def _coerce_types(parsed: dict[str, Any]) -> dict[str, Any]:
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
    return parsed


def _validate_schema(parsed: dict[str, Any]) -> list[str]:
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
    if (parsed.get("reasoning_summary") or "").strip() == "Stage 2 JSON parse failed":
        errors.append("JSON parse failed")
    return errors


def _describe_validation_errors(parsed: dict[str, Any]) -> str:
    errors = _validate_schema(parsed)
    return "; ".join(errors) if errors else "unknown"


def _regex_extract_scores(stage_1_text: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "reasoning_summary": "Scores extracted via regex fallback from Stage 1 text.",
    }

    float_patterns = {
        "clarity": r"(?:CLARITY|clarity)[:\s=]+([01](?:\.\d+)?)",
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
