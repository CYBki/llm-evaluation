"""
RAG-specific evaluation metrics — standalone version.

Six metrics computed independently:
  1. answer_relevancy
  2. hallucination_score
  3. citation_check
  4. completeness
  5. context_precision
  6. context_recall
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
import time as _time
from typing import Any

from rageval_sdk._config import EvalConfig
from rageval_sdk._json_utils import safe_parse_json_object
from rageval_sdk._llm_client import LLMClientError, OpenAILLMClient
from rageval_sdk._prompts import (
    ANSWER_RELEVANCY_JSON_SCHEMA,
    ANSWER_RELEVANCY_SYSTEM_PROMPT,
    CITATION_CHECK_JSON_SCHEMA,
    CITATION_CHECK_SYSTEM_PROMPT,
    COMPLETENESS_JSON_SCHEMA,
    COMPLETENESS_SYSTEM_PROMPT,
    CONTEXT_PRECISION_JSON_SCHEMA,
    CONTEXT_PRECISION_SYSTEM_PROMPT,
    CONTEXT_RECALL_JSON_SCHEMA,
    CONTEXT_RECALL_SYSTEM_PROMPT,
    HALLUCINATION_JSON_SCHEMA,
    HALLUCINATION_SYSTEM_PROMPT,
    build_answer_relevancy_user_prompt,
    build_citation_check_user_prompt,
    build_completeness_user_prompt,
    build_context_precision_user_prompt,
    build_context_recall_user_prompt,
    build_hallucination_user_prompt,
)

logger = logging.getLogger(__name__)

# ── Capped penalty per problematic claim ──────────────────────────────
_HALLUCINATION_UNSUPPORTED_PENALTY = 0.15
_HALLUCINATION_CONTRADICTION_PENALTY = 0.30
_FAITHFULNESS_PER_CLAIM_PENALTY = 0.20


def score_hallucination_claims(
    claims: list[dict[str, Any]] | None,
) -> dict[str, float | None]:
    """Pure scoring function for hallucination claims (capped penalty model)."""
    if not claims:
        return {"hallucination_score": None, "faithfulness": None}

    total_penalty = 0.0
    unfaithful_count = 0
    for item in claims:
        if not isinstance(item, dict):
            continue
        disagreement_type = str(item.get("disagreement_type", "")).lower()
        if disagreement_type == "unsupported claim":
            total_penalty += _HALLUCINATION_UNSUPPORTED_PENALTY
            unfaithful_count += 1
        elif disagreement_type == "confirmed contradiction":
            total_penalty += _HALLUCINATION_CONTRADICTION_PENALTY
            unfaithful_count += 1

    h_score = round(max(0.0, 1.0 - total_penalty), 4)
    faithfulness = round(
        max(0.0, 1.0 - unfaithful_count * _FAITHFULNESS_PER_CLAIM_PENALTY), 4
    )

    return {
        "hallucination_score": max(0.0, min(1.0, h_score)),
        "faithfulness": max(0.0, min(1.0, faithfulness)),
    }


# ── Cosine Similarity ────────────────────────────────────────────────


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(a: list[float]) -> float:
    return math.sqrt(sum(x * x for x in a))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    na, nb = _norm(a), _norm(b)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return _dot(a, b) / (na * nb)


# ── 1. Answer Relevancy ──────────────────────────────────────────────


async def compute_answer_relevancy(
    client: OpenAILLMClient,
    question: str,
    answer: str,
    contexts: list[str],
    config: EvalConfig,
) -> float | None:
    if not client.is_enabled:
        return None

    try:
        resp = await client.chat_completion(
            model=config.rag_metrics_model,
            system_prompt=ANSWER_RELEVANCY_SYSTEM_PROMPT,
            user_prompt=build_answer_relevancy_user_prompt(question, answer, config),
            max_completion_tokens=2048,
            json_schema=ANSWER_RELEVANCY_JSON_SCHEMA,
        )

        parsed = _safe_parse(resp.content)
        statements = parsed.get("statements", [])
        if not isinstance(statements, list) or len(statements) == 0:
            logger.warning(
                "answer_relevancy: no statements extracted. "
                "Raw response (first 500 chars): %s",
                (resp.content or "")[:500],
            )
            return None

        relevant_count = sum(
            1 for s in statements if isinstance(s, dict) and s.get("relevant") is True
        )
        total = len(statements)
        score = round(relevant_count / total, 4) if total > 0 else None

        return max(0.0, min(1.0, score)) if score is not None else None

    except LLMClientError:
        logger.exception("answer_relevancy computation failed")
        return None


# ── 2. Hallucination Score ───────────────────────────────────────────


async def compute_hallucination_rubric(
    client: OpenAILLMClient,
    answer: str,
    contexts: list[str],
    config: EvalConfig,
) -> dict[str, Any]:
    if not client.is_enabled or not contexts:
        return {
            "hallucination_score": None,
            "faithfulness": None,
            "hallucination_claims": [],
        }

    try:
        resp = await client.chat_completion(
            model=config.rag_metrics_model,
            system_prompt=HALLUCINATION_SYSTEM_PROMPT,
            user_prompt=build_hallucination_user_prompt(answer, contexts, config),
            max_completion_tokens=4096,
            json_schema=HALLUCINATION_JSON_SCHEMA,
        )

        parsed = _safe_parse(resp.content)
        claims = parsed.get("disagreement_claims", [])
        if not isinstance(claims, list):
            claims = []

        if not claims:
            logger.warning(
                "hallucination_rubric: no disagreement_claims extracted. "
                "Raw response (first 500 chars): %s",
                (resp.content or "")[:500],
            )
            return {
                "hallucination_score": None,
                "faithfulness": None,
                "hallucination_claims": [],
            }

        scores = score_hallucination_claims(claims)

        return {
            "hallucination_score": scores["hallucination_score"],
            "faithfulness": scores["faithfulness"],
            "hallucination_claims": claims,
        }

    except LLMClientError:
        logger.exception("hallucination rubric computation failed")
        return {
            "hallucination_score": None,
            "faithfulness": None,
            "hallucination_claims": [],
        }


# ── 3. Citation Check ────────────────────────────────────────────────

_CITATION_PATTERN = re.compile(
    r"\[(\d+)\]"
    r"|\[Source\s*(\d+)\]"
    r"|\(bkz\.?\s*context\s*(\d+)\)",
    re.IGNORECASE,
)


def has_citations(answer: str) -> bool:
    return bool(_CITATION_PATTERN.search(answer))


async def compute_citation_check(
    client: OpenAILLMClient,
    answer: str,
    contexts: list[str],
    config: EvalConfig,
) -> float | None:
    if not client.is_enabled:
        return None

    if not has_citations(answer):
        return None

    if not contexts:
        return 0.0

    try:
        resp = await client.chat_completion(
            model=config.rag_metrics_model,
            system_prompt=CITATION_CHECK_SYSTEM_PROMPT,
            user_prompt=build_citation_check_user_prompt(answer, contexts, config),
            max_completion_tokens=1536,
            json_schema=CITATION_CHECK_JSON_SCHEMA,
        )

        parsed = _safe_parse(resp.content)
        citations = parsed.get("citations", [])
        if not isinstance(citations, list) or len(citations) == 0:
            return 1.0

        correct = sum(1 for c in citations if c.get("verdict") == "correct")
        total = len(citations)
        return round(correct / total, 4) if total > 0 else 1.0

    except LLMClientError:
        logger.exception("citation_check computation failed")
        return None


# ── 4. Completeness ──────────────────────────────────────────────────


async def compute_completeness(
    client: OpenAILLMClient,
    question: str,
    answer: str,
    contexts: list[str],
    config: EvalConfig,
) -> dict[str, Any]:
    if not client.is_enabled:
        return {"completeness": None, "key_points": []}

    if not question.strip():
        return {"completeness": None, "key_points": []}

    try:
        resp = await client.chat_completion(
            model=config.rag_metrics_model,
            system_prompt=COMPLETENESS_SYSTEM_PROMPT,
            user_prompt=build_completeness_user_prompt(question, answer, contexts, config),
            max_completion_tokens=2048,
            json_schema=COMPLETENESS_JSON_SCHEMA,
        )

        parsed = _safe_parse(resp.content)
        key_points = parsed.get("key_points", [])
        if not isinstance(key_points, list) or len(key_points) == 0:
            return {"completeness": None, "key_points": []}

        status_weights = {"covered": 1.0, "partially_covered": 0.5, "not_covered": 0.0}
        total_score = sum(
            status_weights.get(kp.get("status", "not_covered"), 0.0)
            for kp in key_points
        )
        total_points = len(key_points)
        score = round(total_score / total_points, 4) if total_points > 0 else None

        return {"completeness": score, "key_points": key_points}

    except LLMClientError:
        logger.exception("completeness computation failed")
        return {"completeness": None, "key_points": []}


# ── 5. Context Precision ─────────────────────────────────────────────


async def compute_context_precision(
    client: OpenAILLMClient,
    question: str,
    contexts: list[str],
    config: EvalConfig,
) -> float | None:
    if not client.is_enabled or not contexts:
        return None

    try:
        resp = await client.chat_completion(
            model=config.rag_metrics_model,
            system_prompt=CONTEXT_PRECISION_SYSTEM_PROMPT,
            user_prompt=build_context_precision_user_prompt(question, contexts, config),
            max_completion_tokens=2048,
            json_schema=CONTEXT_PRECISION_JSON_SCHEMA,
        )

        parsed = _safe_parse(resp.content)
        ctx_items = parsed.get("contexts", [])
        if not isinstance(ctx_items, list) or len(ctx_items) == 0:
            logger.warning(
                "context_precision: no context evaluations returned. "
                "Raw response (first 500 chars): %s",
                (resp.content or "")[:500],
            )
            return None

        relevant_count = sum(
            1 for c in ctx_items if isinstance(c, dict) and c.get("relevant") is True
        )
        total = len(ctx_items)
        return round(relevant_count / total, 4) if total > 0 else None

    except LLMClientError:
        logger.exception("context_precision computation failed")
        return None


# ── 6. Context Recall ────────────────────────────────────────────────


async def compute_context_recall(
    client: OpenAILLMClient,
    question: str,
    contexts: list[str],
    ground_truth: str | None,
    config: EvalConfig,
) -> float | None:
    if not client.is_enabled or not contexts:
        return None

    try:
        resp = await client.chat_completion(
            model=config.rag_metrics_model,
            system_prompt=CONTEXT_RECALL_SYSTEM_PROMPT,
            user_prompt=build_context_recall_user_prompt(
                question, contexts, ground_truth, config
            ),
            max_completion_tokens=2048,
            json_schema=CONTEXT_RECALL_JSON_SCHEMA,
        )

        parsed = _safe_parse(resp.content)
        items = parsed.get("items", [])
        if not isinstance(items, list) or len(items) == 0:
            logger.warning(
                "context_recall: no items returned. Raw response (first 500 chars): %s",
                (resp.content or "")[:500],
            )
            return None

        found_count = sum(
            1
            for item in items
            if isinstance(item, dict) and item.get("verdict") == "found"
        )
        total = len(items)
        return round(found_count / total, 4) if total > 0 else None

    except LLMClientError:
        logger.exception("context_recall computation failed")
        return None


# ── Orchestrator ─────────────────────────────────────────────────────


async def compute_rag_metrics(
    question: str,
    answer: str,
    contexts: list[str] | None,
    ground_truth: str | None,
    client: OpenAILLMClient,
    config: EvalConfig,
) -> dict[str, Any]:
    """Compute all 6 RAG metrics concurrently."""
    ctx = contexts or []

    _t0 = _time.perf_counter()

    async def _timed(name: str, coro):
        t = _time.perf_counter()
        result = await coro
        logger.info(
            "RAG metric '%s' completed in %.1fs", name, _time.perf_counter() - t
        )
        return result

    relevancy_task = asyncio.create_task(
        _timed("relevancy", compute_answer_relevancy(client, question, answer, ctx, config))
    )
    citation_task = asyncio.create_task(
        _timed("citation", compute_citation_check(client, answer, ctx, config))
    )
    hallucination_task = asyncio.create_task(
        _timed("hallucination", compute_hallucination_rubric(client, answer, ctx, config))
    )
    completeness_task = asyncio.create_task(
        _timed("completeness", compute_completeness(client, question, answer, ctx, config))
    )
    ctx_precision_task = asyncio.create_task(
        _timed("ctx_precision", compute_context_precision(client, question, ctx, config))
    )
    ctx_recall_task = asyncio.create_task(
        _timed(
            "ctx_recall", compute_context_recall(client, question, ctx, ground_truth, config)
        )
    )

    relevancy = await relevancy_task
    citation = await citation_task
    hallucination_result = await hallucination_task
    comp_result = await completeness_task
    ctx_precision = await ctx_precision_task
    ctx_recall = await ctx_recall_task

    _t_end = _time.perf_counter()
    logger.info("RAG metrics total: %.1fs", _t_end - _t0)

    _rag_prompt = getattr(client, "_accumulated_prompt_tokens", 0)
    _rag_completion = getattr(client, "_accumulated_completion_tokens", 0)

    return {
        "answer_relevancy": relevancy,
        "hallucination_score": hallucination_result.get("hallucination_score"),
        "faithfulness": hallucination_result.get("faithfulness"),
        "hallucination_claims": hallucination_result.get("hallucination_claims", []),
        "hallucination_prompt_version": config.hallucination_prompt_version,
        "citation_check": citation,
        "completeness": comp_result.get("completeness"),
        "completeness_key_points": comp_result.get("key_points", []),
        "context_precision": ctx_precision,
        "context_recall": ctx_recall,
        "_prompt_tokens": _rag_prompt,
        "_completion_tokens": _rag_completion,
    }


# ── Helpers ──────────────────────────────────────────────────────────


def _safe_parse(content: str) -> dict[str, Any]:
    return safe_parse_json_object(content)
