"""Unit tests for evaluator helper functions."""

import pytest

from app.evaluation.evaluator import (
    _coerce_off_topic_flag,
    _coerce_types,
    _compute_overall_score,
    _regex_extract_scores,
    _safe_parse_json,
    _validate_schema,
    evaluate_trace,
)
from app.evaluation.llm_client import LLMResponse
from app.evaluation.prompts import (
    ANSWER_RELEVANCY_SYSTEM_PROMPT,
    CITATION_CHECK_SYSTEM_PROMPT,
    COMPLETENESS_SYSTEM_PROMPT,
    CONTEXT_PRECISION_SYSTEM_PROMPT,
    CONTEXT_RECALL_SYSTEM_PROMPT,
    HALLUCINATION_SYSTEM_PROMPT,
    STAGE_1_SYSTEM_PROMPT,
    STAGE_2_SYSTEM_PROMPT,
)


class _ScriptedFakeClient:
    def __init__(self, responses_by_system_prompt, *, enabled: bool = True):
        self._responses_by_system_prompt = {
            key: list(value) for key, value in responses_by_system_prompt.items()
        }
        self.is_enabled = enabled
        self.calls: list[dict] = []
        self._accumulated_prompt_tokens = 0
        self._accumulated_completion_tokens = 0

    async def chat_completion(self, **kwargs):
        self.calls.append(kwargs)
        key = kwargs["system_prompt"]
        response = self._responses_by_system_prompt[key].pop(0)
        self._accumulated_prompt_tokens += response.prompt_tokens
        self._accumulated_completion_tokens += response.completion_tokens
        return response


class TestSafeParseJson:
    def test_valid_json(self):
        result = _safe_parse_json('{"clarity": 0.8, "coherence": 0.7}')
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


class TestCoerceOffTopicFlag:
    """Tests for _coerce_off_topic_flag hard-override + LLM trust logic."""

    def test_hard_override_when_relevancy_and_helpfulness_zero(self):
        # Even if LLM says false, scores prove off-topic
        assert _coerce_off_topic_flag(False, 0.0, 0.0) is True

    def test_llm_true_respected(self):
        assert _coerce_off_topic_flag(True, 0.5, 0.5) is True

    def test_llm_false_respected_when_scores_nonzero(self):
        assert _coerce_off_topic_flag(False, 0.5, 0.5) is False

    def test_no_llm_flag_with_zero_scores(self):
        # LLM returned non-bool (None), scores trigger override
        assert _coerce_off_topic_flag(None, 0.0, 0.0) is True

    def test_no_llm_flag_with_nonzero_scores(self):
        assert _coerce_off_topic_flag(None, 0.7, 0.4) is False

    def test_partial_zero_no_override(self):
        # Only one is zero → not enough for override
        assert _coerce_off_topic_flag(False, 0.0, 0.4) is False
        assert _coerce_off_topic_flag(False, 0.5, 0.0) is False


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


class TestValidateSchema:
    def test_valid(self):
        data = {
            "clarity": 0.8,
            "coherence": 0.7,
            "helpfulness": 0.8,
            "overall_score": 0.7,
            "evaluation_confidence": 0.9,
            "is_off_topic": False,
            "is_deflection": False,
            "reasoning_summary": "Good.",
        }
        assert _validate_schema(data) == []

    def test_missing_field(self):
        errors = _validate_schema({"clarity": 0.8})
        assert len(errors) > 0
        assert any("Missing" in e for e in errors)

    def test_wrong_type(self):
        data = {
            "clarity": "not_a_number",
            "coherence": 0.7,
            "helpfulness": 0.8,
            "overall_score": 0.7,
            "evaluation_confidence": 0.9,
            "is_off_topic": False,
            "is_deflection": False,
            "reasoning_summary": "Test.",
        }
        errors = _validate_schema(data)
        assert any("number" in e for e in errors)


class TestRegexExtractScores:
    def test_extract_from_text(self):
        text = """
        CLARITY: 0.8
        COHERENCE: 0.9
        HELPFULNESS: 0.5
        IS_OFF_TOPIC: false
        IS_DEFLECTION: false
        """
        result = _regex_extract_scores(text)
        assert result["clarity"] == 0.8
        assert result["coherence"] == 0.9
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
        rag = {"completeness": 0.8, "answer_relevancy": 0.7}
        score = _compute_overall_score(parsed, rag)
        # Current weights: coherence(0.05), helpfulness(0.15), clarity(0.05),
        #                  completeness(0.10), answer_relevancy(0.15) = total 0.50
        # weighted_sum = 0.05*0.8 + 0.15*0.7 + 0.05*0.9 + 0.10*0.8 + 0.15*0.7 = 0.375
        assert score == pytest.approx(0.375 / 0.50, abs=0.001)

    def test_partial_metrics(self):
        parsed = {"coherence": 0.8, "helpfulness": None, "clarity": None}
        rag = {"completeness": None, "answer_relevancy": 0.6}
        score = _compute_overall_score(parsed, rag)
        # answer_relevancy(0.15), coherence(0.05) → total_weight=0.20
        # weighted_sum = 0.15*0.6 + 0.05*0.8 = 0.13
        assert score == pytest.approx(0.13 / 0.20, abs=0.001)

    def test_no_metrics_falls_back(self):
        parsed = {"overall_score": 0.5}
        rag = {}
        score = _compute_overall_score(parsed, rag)
        assert score == 0.5

    def test_all_none_falls_back(self):
        parsed = {
            "coherence": None,
            "helpfulness": None,
            "clarity": None,
            "overall_score": 0.42,
        }
        rag = {"completeness": None, "answer_relevancy": None}
        score = _compute_overall_score(parsed, rag)
        assert score == 0.42

    def test_rag_completeness_overrides_parsed(self):
        parsed = {
            "coherence": 0.8,
            "helpfulness": 0.8,
            "clarity": 0.8,
            "completeness": 0.3,
        }
        rag = {"completeness": 0.9, "answer_relevancy": 0.8}
        score = _compute_overall_score(parsed, rag)
        # completeness should use 0.9 (rag) not 0.3 (parsed)
        # weights: completeness(0.10), answer_relevancy(0.15), coherence(0.05),
        #          helpfulness(0.15), clarity(0.05) = total 0.50
        expected = (
            0.10 * 0.9 + 0.15 * 0.8 + 0.05 * 0.8 + 0.15 * 0.8 + 0.05 * 0.8
        ) / 0.50
        assert score == pytest.approx(expected, abs=0.001)

    def test_perfect_scores(self):
        parsed = {"coherence": 1.0, "helpfulness": 1.0, "clarity": 1.0}
        rag = {"completeness": 1.0, "answer_relevancy": 1.0}
        score = _compute_overall_score(parsed, rag)
        assert score == pytest.approx(1.0, abs=0.001)

    def test_zero_scores(self):
        parsed = {"coherence": 0.0, "helpfulness": 0.0, "clarity": 0.0}
        rag = {"completeness": 0.0, "answer_relevancy": 0.0}
        score = _compute_overall_score(parsed, rag)
        assert score == pytest.approx(0.0, abs=0.001)

    def test_context_metrics_included(self):
        """When context metrics are present (hallucination missing), score still normalizes correctly."""
        parsed = {"coherence": 0.8, "helpfulness": 0.8, "clarity": 0.8}
        rag = {
            "completeness": 0.8,
            "answer_relevancy": 0.8,
            "context_precision": 0.8,
            "context_recall": 0.8,
        }
        score = _compute_overall_score(parsed, rag)
        # All available metrics are 0.8; normalization preserves 0.8
        assert score == pytest.approx(0.8, abs=0.001)

    def test_context_precision_only(self):
        """Only context_precision available, context_recall None — partial re-weighting."""
        parsed = {"coherence": 1.0, "helpfulness": 1.0, "clarity": 1.0}
        rag = {
            "completeness": 1.0,
            "answer_relevancy": 1.0,
            "context_precision": 0.5,
            "context_recall": None,
        }
        score = _compute_overall_score(parsed, rag)
        # available: answer_relevancy(0.15), completeness(0.10), context_precision(0.10),
        #           helpfulness(0.15), coherence(0.05), clarity(0.05) = total 0.60
        # weighted = 0.15*1 + 0.10*1 + 0.10*0.5 + 0.15*1 + 0.05*1 + 0.05*1 = 0.55
        assert score == pytest.approx(0.55 / 0.60, abs=0.001)

    def test_hallucination_score_influences_overall(self):
        parsed = {"coherence": 1.0, "helpfulness": 1.0, "clarity": 1.0}
        rag = {
            "hallucination_score": 0.0,
            "completeness": 1.0,
            "answer_relevancy": 1.0,
            "context_precision": 1.0,
            "context_recall": 1.0,
        }
        score = _compute_overall_score(parsed, rag)
        # missing faithfulness, citation_check → total_weight = 0.85
        # weighted = 0.15*0 + 0.15*1 + 0.10*1 + 0.10*1 + 0.10*1 + 0.15*1 + 0.05*1 + 0.05*1 = 0.70
        assert score == pytest.approx(0.70 / 0.85, abs=0.001)


class TestEvaluateTraceWithFakeClients:
    @pytest.mark.asyncio
    async def test_uses_injected_clients_end_to_end(self):
        eval_client = _ScriptedFakeClient(
            {
                STAGE_1_SYSTEM_PROMPT: [
                    LLMResponse(
                        content="Stage 1 reasoning",
                        raw={"stage": 1},
                        prompt_tokens=11,
                        completion_tokens=7,
                    )
                ],
                STAGE_2_SYSTEM_PROMPT: [
                    LLMResponse(
                        content='{"clarity": 0.9, "coherence": 0.8, "helpfulness": 0.7, "overall_score": 0.8, "evaluation_confidence": 0.95, "is_off_topic": false, "is_deflection": false, "reasoning_summary": "Good answer."}',
                        raw={"stage": 2},
                        prompt_tokens=13,
                        completion_tokens=5,
                    )
                ],
            }
        )
        rag_client = _ScriptedFakeClient(
            {
                ANSWER_RELEVANCY_SYSTEM_PROMPT: [
                    LLMResponse(
                        content='{"statements": [{"text": "A", "relevant": true}]}',
                        raw={"metric": "answer_relevancy"},
                        prompt_tokens=3,
                        completion_tokens=2,
                    )
                ],
                CITATION_CHECK_SYSTEM_PROMPT: [
                    LLMResponse(
                        content='{"citations": [{"verdict": "correct"}]}',
                        raw={"metric": "citation_check"},
                        prompt_tokens=2,
                        completion_tokens=1,
                    )
                ],
                HALLUCINATION_SYSTEM_PROMPT: [
                    LLMResponse(
                        content='{"disagreement_claims": [{"answer_quote": "A", "disagreement_type": "agreement", "reasoning": "ok"}]}',
                        raw={"metric": "hallucination"},
                        prompt_tokens=5,
                        completion_tokens=4,
                    )
                ],
                COMPLETENESS_SYSTEM_PROMPT: [
                    LLMResponse(
                        content='{"key_points": [{"point": "A", "status": "covered", "evidence": "ctx"}]}',
                        raw={"metric": "completeness"},
                        prompt_tokens=4,
                        completion_tokens=2,
                    )
                ],
                CONTEXT_PRECISION_SYSTEM_PROMPT: [
                    LLMResponse(
                        content='{"contexts": [{"context_index": 0, "relevant": true, "reason": "ok"}]}',
                        raw={"metric": "context_precision"},
                        prompt_tokens=2,
                        completion_tokens=2,
                    )
                ],
                CONTEXT_RECALL_SYSTEM_PROMPT: [
                    LLMResponse(
                        content='{"items": [{"statement": "A", "verdict": "found", "evidence": "ctx"}]}',
                        raw={"metric": "context_recall"},
                        prompt_tokens=2,
                        completion_tokens=2,
                    )
                ],
            }
        )

        result = await evaluate_trace(
            question="What is the Eiffel Tower?",
            answer="It is a tower in Paris [1].",
            contexts=["The Eiffel Tower is in Paris."],
            ground_truth="A tower in Paris.",
            client=eval_client,
            rag_client=rag_client,
        )

        assert result["clarity"] == 0.9
        assert result["coherence"] == 0.8
        assert result["completeness"] == 1.0
        assert result["answer_relevancy"] == 1.0
        assert result["faithfulness"] == 1.0
        assert result["citation_check"] == 1.0
        assert result["prompt_tokens"] == 42
        assert result["completion_tokens"] == 25
        assert len(eval_client.calls) == 2
        assert len(rag_client.calls) == 6

    @pytest.mark.asyncio
    async def test_disabled_injected_client_skips_evaluation(self):
        client = _ScriptedFakeClient({}, enabled=False)

        result = await evaluate_trace(
            question="Q?",
            answer="A.",
            contexts=None,
            client=client,
            rag_client=client,
        )

        assert result["raw_response"]["skipped"] is True
        assert (
            result["reasoning_summary"]
            == "OPENAI_API_KEY not configured; evaluation skipped."
        )
