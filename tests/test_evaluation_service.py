"""Unit tests for evaluation_service helper functions."""

from types import SimpleNamespace

from app.models.evaluation import EvaluationResult, StepEvaluationResult
from app.models.trace import TraceStatus
from app.services.evaluation_result_mapper import (
    apply_result_to_evaluation,
    apply_result_to_step,
    copy_cached_evaluation,
)
from app.services.evaluation_service import (
    _compute_content_hash,
    _extract_steps,
    _is_successful_result,
)


class TestTraceStatus:
    def test_expected_values(self):
        assert TraceStatus.PENDING.value == "pending"
        assert TraceStatus.COMPLETED.value == "completed"
        assert TraceStatus.FAILED.value == "failed"


class TestIsSuccessfulResult:
    def test_list_with_valid_items(self):
        assert _is_successful_result({"raw_response": [{"model": "gpt-5.2"}]}) is True

    def test_list_with_failed_item(self):
        assert _is_successful_result({"raw_response": [{"failed": True}]}) is False

    def test_list_with_skipped_item(self):
        assert _is_successful_result({"raw_response": [{"skipped": True}]}) is False

    def test_empty_list(self):
        assert _is_successful_result({"raw_response": []}) is False

    def test_dict_ok(self):
        assert _is_successful_result({"raw_response": {"model": "gpt-5.2"}}) is True

    def test_dict_failed(self):
        assert _is_successful_result({"raw_response": {"failed": True}}) is False

    def test_none_raw(self):
        assert _is_successful_result({"raw_response": None}) is False

    def test_missing_raw(self):
        assert _is_successful_result({}) is False


class TestEvaluationResultMapper:
    def test_apply_result_to_evaluation_maps_trace_only_fields(self):
        evaluation = EvaluationResult(trace_id=None)
        result = {
            "clarity": 0.9,
            "overall_score": 0.8,
            "raw_response": [{"ok": True}],
            "prompt_tokens": 12,
            "completion_tokens": 5,
            "hallucination_claims": [{"answer_quote": "A"}],
        }

        apply_result_to_evaluation(evaluation, result)

        assert evaluation.clarity == 0.9
        assert evaluation.overall_score == 0.8
        assert evaluation.raw_response == [{"ok": True}]
        assert evaluation.prompt_tokens == 12
        assert evaluation.completion_tokens == 5
        assert evaluation.hallucination_claims == [{"answer_quote": "A"}]
        assert evaluation.faithfulness_claims == [{"answer_quote": "A"}]

    def test_apply_result_to_step_ignores_trace_only_fields(self):
        step_eval = StepEvaluationResult(trace_id=None, step_index=0, agent_name="a1")
        result = {
            "clarity": 0.7,
            "raw_response": [{"ok": True}],
            "prompt_tokens": 12,
        }

        apply_result_to_step(step_eval, result)

        assert step_eval.clarity == 0.7
        assert not hasattr(step_eval, "raw_response")
        assert not hasattr(step_eval, "prompt_tokens")

    def test_copy_cached_evaluation_reuses_cached_fields(self):
        source = EvaluationResult(trace_id=None)
        target = EvaluationResult(trace_id=None)
        source.clarity = 0.8
        source.reasoning_summary = "cached"
        source.content_hash = "abc"
        source.evaluation_duration_ms = 321

        copy_cached_evaluation(source, target)

        assert target.clarity == 0.8
        assert target.reasoning_summary == "cached"
        assert target.content_hash == "abc"
        assert target.evaluation_duration_ms == 321


class TestEvaluationServiceHelpers:
    def test_compute_content_hash_is_stable(self):
        first = _compute_content_hash("Q?", "A.", ["ctx1"], "GT")
        second = _compute_content_hash("Q?", "A.", ["ctx1"], "GT")
        assert first == second

    def test_compute_content_hash_changes_when_input_changes(self):
        first = _compute_content_hash("Q?", "A.", ["ctx1"], "GT")
        second = _compute_content_hash("Q?", "B.", ["ctx1"], "GT")
        assert first != second

    def test_extract_steps_returns_list_from_trace_metadata(self):
        trace = SimpleNamespace(meta={"steps": [{"step_index": 0}]})
        assert _extract_steps(trace) == [{"step_index": 0}]

    def test_extract_steps_returns_none_for_invalid_metadata(self):
        assert _extract_steps(SimpleNamespace(meta=None)) is None
        assert _extract_steps(SimpleNamespace(meta={"steps": "bad"})) is None
