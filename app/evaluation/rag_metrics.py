"""
RAG-specific evaluation metrics.

Five metrics computed independently from the two-stage rubric pipeline:
  1. answer_relevancy  – statement-level relevancy classification
  2. faithfulness      – LLM claim extraction + context verification
  3. hallucination_score – derived from faithfulness (1 - unsupported ratio)
  4. citation_check    – citation tag verification against contexts
  5. completeness      – key-point extraction + coverage verification
"""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Any

from app.config import settings
from app.evaluation.llm_client import LLMClientError, OpenAILLMClient
from app.evaluation.prompts import (
    ANSWER_RELEVANCY_JSON_SCHEMA,
    ANSWER_RELEVANCY_SYSTEM_PROMPT,
    CITATION_CHECK_JSON_SCHEMA,
    CITATION_CHECK_SYSTEM_PROMPT,
    COMPLETENESS_JSON_SCHEMA,
    COMPLETENESS_SYSTEM_PROMPT,
    FAITHFULNESS_JSON_SCHEMA,
    FAITHFULNESS_SYSTEM_PROMPT,
    build_answer_relevancy_user_prompt,
    build_citation_check_user_prompt,
    build_completeness_user_prompt,
    build_faithfulness_user_prompt,
)

logger = logging.getLogger(__name__)


# ── Cosine Similarity (pure Python, no numpy needed) ────────────────────

def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(a: list[float]) -> float:
    return math.sqrt(sum(x * x for x in a))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors. Returns 0.0 on degenerate input."""
    na, nb = _norm(a), _norm(b)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return _dot(a, b) / (na * nb)


# ── 1. Answer Relevancy (Statement-Level Relevancy) ─────────────────

async def compute_answer_relevancy(
    client: OpenAILLMClient,
    question: str,
    answer: str,
    contexts: list[str],
) -> float | None:
    """
    Compute answer relevancy using the DeepEval statement-level method.

    Strategy:
    1. LLM decomposes the answer into individual statements.
    2. LLM classifies each statement as relevant/not_relevant to the question.
    3. Score = number of relevant statements / total statements.

    Returns a float in [0.0, 1.0] or None on failure.
    """
    if not client.is_enabled:
        return None

    try:
        resp = await client.chat_completion(
            model=settings.rag_metrics_model,
            system_prompt=ANSWER_RELEVANCY_SYSTEM_PROMPT,
            user_prompt=build_answer_relevancy_user_prompt(question, answer),
            max_completion_tokens=2048,
            json_schema=ANSWER_RELEVANCY_JSON_SCHEMA,
        )

        parsed = _safe_parse(resp.content)
        statements = parsed.get("statements", [])
        if not isinstance(statements, list) or len(statements) == 0:
            logger.warning("answer_relevancy: no statements extracted")
            return None

        relevant_count = sum(
            1 for s in statements
            if isinstance(s, dict) and s.get("relevant") is True
        )
        total = len(statements)
        score = round(relevant_count / total, 4) if total > 0 else None

        return max(0.0, min(1.0, score)) if score is not None else None

    except LLMClientError:
        logger.exception("answer_relevancy computation failed")
        return None


# ── 2. Faithfulness (Claim Extraction + Verification) ──────────────────

async def compute_faithfulness(
    client: OpenAILLMClient,
    answer: str,
    contexts: list[str],
) -> dict[str, Any]:
    """
    Extract factual claims from the answer and verify each against contexts.

    Returns:
        {
            "faithfulness": float | None,       # supported / total
            "claims": [{"claim": str, "verdict": str, "reason": str}, ...],
        }
    """
    if not client.is_enabled or not contexts:
        return {"faithfulness": None, "claims": []}

    try:
        resp = await client.chat_completion(
            model=settings.rag_metrics_model,
            system_prompt=FAITHFULNESS_SYSTEM_PROMPT,
            user_prompt=build_faithfulness_user_prompt(answer, contexts),
            max_completion_tokens=2048,
            json_schema=FAITHFULNESS_JSON_SCHEMA,
        )

        parsed = _safe_parse(resp.content)
        claims = parsed.get("claims", [])
        if not isinstance(claims, list) or len(claims) == 0:
            return {"faithfulness": None, "claims": []}

        supported = sum(1 for c in claims if c.get("verdict") == "supported")
        total = len(claims)
        score = round(supported / total, 4) if total > 0 else None

        return {"faithfulness": score, "claims": claims}

    except LLMClientError:
        logger.exception("faithfulness computation failed")
        return {"faithfulness": None, "claims": []}


# ── 3. Hallucination Score ─────────────────────────────────────────────

def compute_hallucination_score(claims: list[dict]) -> float | None:
    """
    Derive hallucination score from faithfulness claims.

    hallucination_score = 1.0 - (unsupported_or_contradicted / total)
    1.0 = no hallucination (all claims supported)  → GOOD
    0.0 = everything hallucinated                   → BAD

    Returns None if no claims available.
    """
    if not claims:
        return None

    total = len(claims)
    hallucinated = sum(
        1 for c in claims if c.get("verdict") in ("not_supported", "contradicted")
    )
    return round(1.0 - (hallucinated / total), 4) if total > 0 else None


# ── 4. Citation Check ──────────────────────────────────────────────────

_CITATION_PATTERN = re.compile(
    r"\[(\d+)\]"            # [1], [2], ...
    r"|\[Source\s*(\d+)\]"  # [Source 1], [Source 2], ...
    r"|\(bkz\.?\s*context\s*(\d+)\)"  # (bkz. context 1)
    , re.IGNORECASE
)


def has_citations(answer: str) -> bool:
    """Check if the answer contains any citation-like patterns."""
    return bool(_CITATION_PATTERN.search(answer))


async def compute_citation_check(
    client: OpenAILLMClient,
    answer: str,
    contexts: list[str],
) -> float | None:
    """
    Check if citations in the answer correctly reference context content.

    If no citations exist in the answer → returns 1.0 (no citations to be wrong about).
    Otherwise → correct_citations / total_citations.
    Returns None on failure.
    """
    if not client.is_enabled:
        return None

    # If no citation patterns exist, metric is not applicable
    if not has_citations(answer):
        return None

    if not contexts:
        # Citations exist but no contexts → all citations are wrong
        return 0.0

    try:
        resp = await client.chat_completion(
            model=settings.rag_metrics_model,
            system_prompt=CITATION_CHECK_SYSTEM_PROMPT,
            user_prompt=build_citation_check_user_prompt(answer, contexts),
            max_completion_tokens=1024,
            json_schema=CITATION_CHECK_JSON_SCHEMA,
        )

        parsed = _safe_parse(resp.content)
        citations = parsed.get("citations", [])
        if not isinstance(citations, list) or len(citations) == 0:
            return 1.0  # LLM found no citations to verify

        correct = sum(1 for c in citations if c.get("verdict") == "correct")
        total = len(citations)
        return round(correct / total, 4) if total > 0 else 1.0

    except LLMClientError:
        logger.exception("citation_check computation failed")
        return None


# ── 5. Completeness (Key-Point Extraction + Verification) ────────────────

async def compute_completeness(
    client: OpenAILLMClient,
    question: str,
    answer: str,
    contexts: list[str],
) -> dict[str, Any]:
    """
    Compute completeness by extracting key points from the question
    and verifying which ones the answer covers.

    Returns:
        {
            "completeness": float | None,   # weighted coverage score
            "key_points": [...],
        }
    """
    if not client.is_enabled:
        return {"completeness": None, "key_points": []}

    if not question.strip():
        return {"completeness": None, "key_points": []}

    try:
        resp = await client.chat_completion(
            model=settings.rag_metrics_model,
            system_prompt=COMPLETENESS_SYSTEM_PROMPT,
            user_prompt=build_completeness_user_prompt(question, answer, contexts),
            max_completion_tokens=1024,
            json_schema=COMPLETENESS_JSON_SCHEMA,
        )

        parsed = _safe_parse(resp.content)
        key_points = parsed.get("key_points", [])
        if not isinstance(key_points, list) or len(key_points) == 0:
            return {"completeness": None, "key_points": []}

        # Score: covered=1.0, partially_covered=0.5, not_covered=0.0
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


# ── Orchestrator ───────────────────────────────────────────────────────

async def compute_rag_metrics(
    question: str,
    answer: str,
    contexts: list[str] | None,
) -> dict[str, Any]:
    """
    Compute all 5 RAG metrics and return a flat dict.

    Returns:
        {
            "answer_relevancy": float | None,
            "faithfulness": float | None,
            "hallucination_score": float | None,
            "citation_check": float | None,
            "faithfulness_claims": list[dict],
            "completeness": float | None,
            "completeness_key_points": list[dict],
        }
    """
    client = OpenAILLMClient()
    ctx = contexts or []

    # Run all independent metrics concurrently
    import asyncio

    relevancy_task = asyncio.create_task(
        compute_answer_relevancy(client, question, answer, ctx)
    )
    faithfulness_task = asyncio.create_task(
        compute_faithfulness(client, answer, ctx)
    )
    citation_task = asyncio.create_task(
        compute_citation_check(client, answer, ctx)
    )
    completeness_task = asyncio.create_task(
        compute_completeness(client, question, answer, ctx)
    )

    relevancy = await relevancy_task
    faith_result = await faithfulness_task
    citation = await citation_task
    comp_result = await completeness_task

    # Hallucination is derived from faithfulness claims (no extra LLM call)
    hallucination = compute_hallucination_score(faith_result.get("claims", []))

    return {
        "answer_relevancy": relevancy,
        "faithfulness": faith_result.get("faithfulness"),
        "hallucination_score": hallucination,
        "citation_check": citation,
        "faithfulness_claims": faith_result.get("claims", []),
        "completeness": comp_result.get("completeness"),
        "completeness_key_points": comp_result.get("key_points", []),
    }


# ── Helpers ────────────────────────────────────────────────────────────

def _safe_parse(content: str) -> dict[str, Any]:
    """Best-effort JSON parse from LLM output."""
    raw = (content or "").strip()

    # Try direct parse
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Strip markdown fences
    if raw.startswith("```"):
        lines = raw.splitlines()
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            body = "\n".join(lines[1:-1]).strip()
            try:
                parsed = json.loads(body)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

    # Extract outermost { ... }
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(raw[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    return {}
