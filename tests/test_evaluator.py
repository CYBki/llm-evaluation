"""Unit tests for evaluator helper functions."""

import pytest

from app.evaluation.evaluator import (
    _coerce_types,
    _compute_overall_score,
    _regex_extract_scores,
    _safe_parse_json,
    _validate_schema,
)


class TestSafeParseJson:
    def test_valid_json(self):
        result = _safe_parse_json('{"clarity": 0.8, "specificity": 0.7}')
        assert result["clarity"] == 0.8

    def test_json_in_code_fence(self):
        raw = '```json\n{"clarity": 0.5}\n```'
        result = _safe_parse_json(raw)
        assert result["clarity"] == 0.5

    def test_json_with_surrounding_text(self):
        raw = 'Here is the result: {"clarity": 0.9} end'
        result = _safe_parse_json(raw)
        assert result["clarity"] == 0.9

    def test_invalid_returns_fallback(self):
        result = _safe_parse_json("not json at all")
        assert result["reasoning_summary"] == "Stage 2 JSON parse failed"

    def test_empty_string(self):
        result = _safe_parse_json("")
        assert "reasoning_summary" in result

    def test_none_input(self):
        result = _safe_parse_json(None)
        assert "reasoning_summary" in result


class TestCoerceTypes:
    def test_clamp_float_above_1(self):
        result = _coerce_types({"clarity": 1.5})
        assert result["clarity"] == 1.0

    def test_clamp_float_below_0(self):
        result = _coerce_types({"clarity": -0.3})
        assert result["clarity"] == 0.0

    def test_string_boolean(self):
        result = _coerce_types({"is_off_topic": "true"})
        assert result["is_off_topic"] is True

    def test_string_boolean_turkish(self):
        result = _coerce_types({"is_deflection": "evet"})
        assert result["is_deflection"] is True

    def test_non_list_disagreement(self):
        result = _coerce_types({"disagreement_claims": "not a list"})
        assert result["disagreement_claims"] == []


class TestValidateSchema:
    def test_valid(self):
        data = {
            "clarity": 0.8, "specificity": 0.7, "completeness": 0.6,
            "coherence": 0.7, "helpfulness": 0.8, "overall_score": 0.7,
            "evaluation_confidence": 0.9, "is_off_topic": False,
            "is_deflection": False, "reasoning_summary": "Good.",
            "disagreement_claims": [],
        }
        assert _validate_schema(data) == []

    def test_missing_field(self):
        errors = _validate_schema({"clarity": 0.8})
        assert len(errors) > 0
        assert any("Missing" in e for e in errors)

    def test_wrong_type(self):
        data = {
            "clarity": "not_a_number", "specificity": 0.7, "completeness": 0.6,
            "coherence": 0.7, "helpfulness": 0.8, "overall_score": 0.7,
            "evaluation_confidence": 0.9, "is_off_topic": False,
            "is_deflection": False, "reasoning_summary": "Test.",
            "disagreement_claims": [],
        }
        errors = _validate_schema(data)
        assert any("number" in e for e in errors)


class TestRegexExtractScores:
    def test_extract_from_text(self):
        text = """
        CLARITY: 0.8
        SPECIFICITY: 0.7
        COMPLETENESS: 0.6
        COHERENCE: 0.9
        HELPFULNESS: 0.5
        IS_OFF_TOPIC: false
        IS_DEFLECTION: false
        """
        result = _regex_extract_scores(text)
        assert result["clarity"] == 0.8
        assert result["specificity"] == 0.7
        assert result["overall_score"] is not None

    def test_no_scores(self):
        result = _regex_extract_scores("this has no scores")
        assert result.get("overall_score") is None

    def test_clamped(self):
        # Regex only matches 0.x or 1.x values, so out-of-range won't happen
        text = "CLARITY: 0.99"
        result = _regex_extract_scores(text)
        assert 0.0 <= result["clarity"] <= 1.0


# ── _compute_overall_score ─────────────────────────────────────────────

class TestComputeOverallScore:
    def test_full_metrics(self):
        parsed = {"coherence": 0.8, "helpfulness": 0.7, "clarity": 0.9}
        rag = {"faithfulness": 0.9, "completeness": 0.8, "answer_relevancy": 0.7}
        score = _compute_overall_score(parsed, rag)
        # 6 of 8 metrics available; total_weight = 0.20+0.15+0.15+0.10+0.10+0.05 = 0.75
        # weighted_sum = 0.20*0.9 + 0.15*0.8 + 0.15*0.7 + 0.10*0.8 + 0.10*0.7 + 0.05*0.9 = 0.60
        assert score == pytest.approx(0.60 / 0.75, abs=0.001)

    def test_partial_metrics(self):
        parsed = {"coherence": 0.8, "helpfulness": None, "clarity": None}
        rag = {"faithfulness": 1.0, "completeness": None, "answer_relevancy": 0.6}
        score = _compute_overall_score(parsed, rag)
        # faithfulness(0.20), answer_relevancy(0.15), coherence(0.10) → total_weight=0.45
        # weighted_sum = 0.20*1.0 + 0.15*0.6 + 0.10*0.8 = 0.37
        assert score == pytest.approx(0.37 / 0.45, abs=0.001)

    def test_no_metrics_falls_back(self):
        parsed = {"overall_score": 0.5}
        rag = {}
        score = _compute_overall_score(parsed, rag)
        assert score == 0.5

    def test_all_none_falls_back(self):
        parsed = {"coherence": None, "helpfulness": None, "clarity": None, "overall_score": 0.42}
        rag = {"faithfulness": None, "completeness": None, "answer_relevancy": None}
        score = _compute_overall_score(parsed, rag)
        assert score == 0.42

    def test_rag_completeness_overrides_parsed(self):
        parsed = {"coherence": 0.8, "helpfulness": 0.8, "clarity": 0.8, "completeness": 0.3}
        rag = {"faithfulness": 0.8, "completeness": 0.9, "answer_relevancy": 0.8}
        score = _compute_overall_score(parsed, rag)
        # completeness should use 0.9 (rag) not 0.3 (parsed)
        # total_weight = 0.20+0.15+0.15+0.10+0.10+0.05 = 0.75
        expected = (0.20*0.8 + 0.15*0.9 + 0.15*0.8 + 0.10*0.8 + 0.10*0.8 + 0.05*0.8) / 0.75
        assert score == pytest.approx(expected, abs=0.001)

    def test_perfect_scores(self):
        parsed = {"coherence": 1.0, "helpfulness": 1.0, "clarity": 1.0}
        rag = {"faithfulness": 1.0, "completeness": 1.0, "answer_relevancy": 1.0}
        score = _compute_overall_score(parsed, rag)
        assert score == pytest.approx(1.0, abs=0.001)

    def test_zero_scores(self):
        parsed = {"coherence": 0.0, "helpfulness": 0.0, "clarity": 0.0}
        rag = {"faithfulness": 0.0, "completeness": 0.0, "answer_relevancy": 0.0}
        score = _compute_overall_score(parsed, rag)
        assert score == pytest.approx(0.0, abs=0.001)

    def test_context_metrics_included(self):
        """When context_precision and context_recall are present, all 8 weights are used."""
        parsed = {"coherence": 0.8, "helpfulness": 0.8, "clarity": 0.8}
        rag = {
            "faithfulness": 0.8, "completeness": 0.8, "answer_relevancy": 0.8,
            "context_precision": 0.8, "context_recall": 0.8,
        }
        score = _compute_overall_score(parsed, rag)
        # All 8 metrics = 0.8, all weights sum to 1.0 → score = 0.8
        assert score == pytest.approx(0.8, abs=0.001)

    def test_context_precision_only(self):
        """Only context_precision available, context_recall None — partial re-weighting."""
        parsed = {"coherence": 1.0, "helpfulness": 1.0, "clarity": 1.0}
        rag = {
            "faithfulness": 1.0, "completeness": 1.0, "answer_relevancy": 1.0,
            "context_precision": 0.5, "context_recall": None,
        }
        score = _compute_overall_score(parsed, rag)
        # 7 of 8 metrics, total_weight = 1.0 - 0.10 = 0.90
        # weighted = 0.20 + 0.15 + 0.15 + 0.15*0.5 + 0.10 + 0.10 + 0.05 = 0.825
        assert score == pytest.approx(0.825 / 0.90, abs=0.001)
