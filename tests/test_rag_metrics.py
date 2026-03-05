"""Unit tests for RAG-specific evaluation metrics."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.evaluation.rag_metrics import (
    compute_context_precision,
    compute_context_recall,
    score_hallucination_claims,
    cosine_similarity,
    has_citations,
    _safe_parse,
)


# ── cosine_similarity ──────────────────────────────────────────────────


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector_returns_0(self):
        a = [0.0, 0.0, 0.0]
        b = [1.0, 2.0, 3.0]
        assert cosine_similarity(a, b) == 0.0

    def test_both_zero_vectors(self):
        a = [0.0, 0.0]
        b = [0.0, 0.0]
        assert cosine_similarity(a, b) == 0.0

    def test_similar_vectors_high_score(self):
        a = [1.0, 2.0, 3.0]
        b = [1.1, 2.1, 3.1]
        sim = cosine_similarity(a, b)
        assert sim > 0.99

    def test_different_magnitude_same_direction(self):
        a = [1.0, 0.0]
        b = [100.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(1.0)


# ── score_hallucination_claims (capped penalty model) ──────────────────


class TestScoreHallucinationClaims:
    def test_all_agreement(self):
        """All claims are agreement → no penalty → score 1.0."""
        claims = [
            {"answer_quote": "A", "disagreement_type": "agreement", "reasoning": "ok"},
            {"answer_quote": "B", "disagreement_type": "agreement", "reasoning": "ok"},
        ]
        result = score_hallucination_claims(claims)
        assert result["hallucination_score"] == 1.0
        assert result["faithfulness"] == 1.0

    def test_single_unsupported(self):
        """One unsupported claim → penalty 0.15 → score 0.85."""
        claims = [
            {"answer_quote": "A", "disagreement_type": "agreement", "reasoning": "ok"},
            {
                "answer_quote": "B",
                "disagreement_type": "unsupported claim",
                "reasoning": "no info",
            },
        ]
        result = score_hallucination_claims(claims)
        assert result["hallucination_score"] == pytest.approx(0.85)
        assert result["faithfulness"] == pytest.approx(0.8)

    def test_single_contradiction(self):
        """One contradiction → penalty 0.30 → score 0.70."""
        claims = [
            {
                "answer_quote": "A",
                "disagreement_type": "confirmed contradiction",
                "reasoning": "wrong",
            },
        ]
        result = score_hallucination_claims(claims)
        assert result["hallucination_score"] == pytest.approx(0.7)
        assert result["faithfulness"] == pytest.approx(0.8)

    def test_mixed_penalties(self):
        """1 unsupported + 1 contradiction → penalty 0.15 + 0.30 = 0.45 → score 0.55."""
        claims = [
            {"answer_quote": "A", "disagreement_type": "agreement", "reasoning": "ok"},
            {
                "answer_quote": "B",
                "disagreement_type": "unsupported claim",
                "reasoning": "no info",
            },
            {
                "answer_quote": "C",
                "disagreement_type": "confirmed contradiction",
                "reasoning": "wrong",
            },
        ]
        result = score_hallucination_claims(claims)
        assert result["hallucination_score"] == pytest.approx(0.55)
        # faithfulness: 2 unfaithful → 1.0 - 2*0.20 = 0.60
        assert result["faithfulness"] == pytest.approx(0.6)

    def test_penalty_floors_at_zero(self):
        """Many penalties → score floors at 0.0, never goes negative."""
        claims = [
            {
                "answer_quote": "A",
                "disagreement_type": "confirmed contradiction",
                "reasoning": "x",
            },
            {
                "answer_quote": "B",
                "disagreement_type": "confirmed contradiction",
                "reasoning": "x",
            },
            {
                "answer_quote": "C",
                "disagreement_type": "confirmed contradiction",
                "reasoning": "x",
            },
            {
                "answer_quote": "D",
                "disagreement_type": "confirmed contradiction",
                "reasoning": "x",
            },
            {
                "answer_quote": "E",
                "disagreement_type": "confirmed contradiction",
                "reasoning": "x",
            },
        ]
        result = score_hallucination_claims(claims)
        # 5 × 0.30 = 1.50 penalty → max(0, 1-1.50) = 0.0
        assert result["hallucination_score"] == 0.0
        # 5 × 0.20 = 1.00 penalty → max(0, 1-1.00) = 0.0
        assert result["faithfulness"] == 0.0

    def test_empty_claims(self):
        result = score_hallucination_claims([])
        assert result["hallucination_score"] is None
        assert result["faithfulness"] is None

    def test_none_claims(self):
        result = score_hallucination_claims(None)
        assert result["hallucination_score"] is None
        assert result["faithfulness"] is None

    def test_agreement_claims_dont_affect_score(self):
        """Adding more agreement claims doesn't change the score."""
        base_claims = [
            {
                "answer_quote": "X",
                "disagreement_type": "unsupported claim",
                "reasoning": "n/a",
            },
        ]
        many_agreements = base_claims + [
            {
                "answer_quote": f"A{i}",
                "disagreement_type": "agreement",
                "reasoning": "ok",
            }
            for i in range(10)
        ]
        result_base = score_hallucination_claims(base_claims)
        result_many = score_hallucination_claims(many_agreements)
        assert result_base["hallucination_score"] == result_many["hallucination_score"]


# ── has_citations ──────────────────────────────────────────────────────


class TestHasCitations:
    def test_bracket_number(self):
        assert has_citations("The answer is correct [1].") is True

    def test_source_format(self):
        assert has_citations("According to [Source 2], this is true.") is True

    def test_bkz_format(self):
        assert has_citations("Detaylar icin (bkz. context 1) bakiniz.") is True

    def test_no_citation(self):
        assert has_citations("This is a normal answer without any references.") is False

    def test_empty_string(self):
        assert has_citations("") is False

    def test_bracket_text_not_number(self):
        # [abc] is NOT a citation pattern
        assert has_citations("See [abc] for details.") is False

    def test_multiple_citations(self):
        assert has_citations("See [1] and [2] and [3].") is True


# ── _safe_parse ────────────────────────────────────────────────────────


class TestSafeParse:
    def test_valid_json(self):
        result = _safe_parse('{"claims": []}')
        assert result == {"claims": []}

    def test_json_with_markdown_fences(self):
        result = _safe_parse('```json\n{"claims": []}\n```')
        assert result == {"claims": []}

    def test_json_embedded_in_text(self):
        result = _safe_parse('Here is the result: {"claims": [{"a": 1}]}')
        assert result == {"claims": [{"a": 1}]}

    def test_empty_string(self):
        result = _safe_parse("")
        assert result == {}

    def test_none_input(self):
        result = _safe_parse(None)
        assert result == {}

    def test_invalid_json(self):
        result = _safe_parse("not json at all")
        assert result == {}

    def test_nested_json(self):
        raw = '{"claims": [{"claim": "X", "verdict": "supported", "reason": "ok"}]}'
        result = _safe_parse(raw)
        assert len(result["claims"]) == 1
        assert result["claims"][0]["verdict"] == "supported"


# ── compute_context_precision (unit-level — mocked LLM) ───────────────


class TestComputeContextPrecision:
    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_all_relevant(self):
        mock_client = MagicMock()
        mock_client.is_enabled = True
        resp = MagicMock()
        resp.content = '{"contexts": [{"context_index": 0, "relevant": true, "reason": "ok"}, {"context_index": 1, "relevant": true, "reason": "ok"}]}'
        mock_client.chat_completion = AsyncMock(return_value=resp)

        result = self._run(
            compute_context_precision(mock_client, "What is X?", ["ctx1", "ctx2"])
        )
        assert result == pytest.approx(1.0)

    def test_none_relevant(self):
        mock_client = MagicMock()
        mock_client.is_enabled = True
        resp = MagicMock()
        resp.content = '{"contexts": [{"context_index": 0, "relevant": false, "reason": "off"}, {"context_index": 1, "relevant": false, "reason": "off"}]}'
        mock_client.chat_completion = AsyncMock(return_value=resp)

        result = self._run(
            compute_context_precision(mock_client, "What is X?", ["ctx1", "ctx2"])
        )
        assert result == pytest.approx(0.0)

    def test_partial_relevant(self):
        mock_client = MagicMock()
        mock_client.is_enabled = True
        resp = MagicMock()
        resp.content = '{"contexts": [{"context_index": 0, "relevant": true, "reason": "ok"}, {"context_index": 1, "relevant": false, "reason": "off"}, {"context_index": 2, "relevant": true, "reason": "ok"}]}'
        mock_client.chat_completion = AsyncMock(return_value=resp)

        result = self._run(
            compute_context_precision(mock_client, "Q?", ["a", "b", "c"])
        )
        assert result == pytest.approx(2 / 3, abs=0.001)

    def test_empty_contexts_returns_none(self):
        mock_client = MagicMock()
        mock_client.is_enabled = True
        result = self._run(compute_context_precision(mock_client, "Q?", []))
        assert result is None

    def test_client_disabled_returns_none(self):
        mock_client = MagicMock()
        mock_client.is_enabled = False
        result = self._run(compute_context_precision(mock_client, "Q?", ["ctx1"]))
        assert result is None

    def test_malformed_response_returns_none(self):
        mock_client = MagicMock()
        mock_client.is_enabled = True
        resp = MagicMock()
        resp.content = '{"contexts": []}'
        mock_client.chat_completion = AsyncMock(return_value=resp)

        result = self._run(compute_context_precision(mock_client, "Q?", ["ctx1"]))
        assert result is None


class TestComputeContextRecall:
    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_all_found(self):
        mock_client = MagicMock()
        mock_client.is_enabled = True
        resp = MagicMock()
        resp.content = '{"items": [{"statement": "A", "verdict": "found", "evidence": "ctx1"}, {"statement": "B", "verdict": "found", "evidence": "ctx2"}]}'
        mock_client.chat_completion = AsyncMock(return_value=resp)

        result = self._run(
            compute_context_recall(mock_client, "Q?", ["ctx1"], "A and B")
        )
        assert result == pytest.approx(1.0)

    def test_none_found(self):
        mock_client = MagicMock()
        mock_client.is_enabled = True
        resp = MagicMock()
        resp.content = '{"items": [{"statement": "A", "verdict": "not_found", "evidence": ""}, {"statement": "B", "verdict": "not_found", "evidence": ""}]}'
        mock_client.chat_completion = AsyncMock(return_value=resp)

        result = self._run(
            compute_context_recall(mock_client, "Q?", ["ctx1"], "A and B")
        )
        assert result == pytest.approx(0.0)

    def test_partial_found(self):
        mock_client = MagicMock()
        mock_client.is_enabled = True
        resp = MagicMock()
        resp.content = '{"items": [{"statement": "A", "verdict": "found", "evidence": "ok"}, {"statement": "B", "verdict": "not_found", "evidence": ""}, {"statement": "C", "verdict": "found", "evidence": "ok"}]}'
        mock_client.chat_completion = AsyncMock(return_value=resp)

        result = self._run(compute_context_recall(mock_client, "Q?", ["ctx1"], "A B C"))
        assert result == pytest.approx(2 / 3, abs=0.001)

    def test_no_ground_truth_still_works(self):
        """Without ground_truth, the model extracts key needs from the question."""
        mock_client = MagicMock()
        mock_client.is_enabled = True
        resp = MagicMock()
        resp.content = (
            '{"items": [{"statement": "need1", "verdict": "found", "evidence": "ctx"}]}'
        )
        mock_client.chat_completion = AsyncMock(return_value=resp)

        result = self._run(compute_context_recall(mock_client, "Q?", ["ctx1"], None))
        assert result == pytest.approx(1.0)

    def test_empty_contexts_returns_none(self):
        mock_client = MagicMock()
        mock_client.is_enabled = True
        result = self._run(compute_context_recall(mock_client, "Q?", [], "GT"))
        assert result is None

    def test_client_disabled_returns_none(self):
        mock_client = MagicMock()
        mock_client.is_enabled = False
        result = self._run(compute_context_recall(mock_client, "Q?", ["ctx1"], "GT"))
        assert result is None
