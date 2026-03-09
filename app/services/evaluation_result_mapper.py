from app.models.evaluation import EvaluationResult, StepEvaluationResult

_COMMON_RESULT_FIELD_MAP = (
    ("clarity", "clarity"),
    ("is_off_topic", "is_off_topic"),
    ("completeness", "completeness"),
    ("coherence", "coherence"),
    ("helpfulness", "helpfulness"),
    ("is_deflection", "is_deflection"),
    ("overall_score", "overall_score"),
    ("evaluation_confidence", "evaluation_confidence"),
    ("reasoning_summary", "reasoning_summary"),
    ("answer_relevancy", "answer_relevancy"),
    ("faithfulness", "faithfulness"),
    ("hallucination_score", "hallucination_score"),
    ("citation_check", "citation_check"),
    ("faithfulness_claims", "hallucination_claims"),
    ("hallucination_claims", "hallucination_claims"),
    ("completeness_key_points", "completeness_key_points"),
    ("context_precision", "context_precision"),
    ("context_recall", "context_recall"),
    ("model_used", "model_used"),
)

_EVALUATION_ONLY_FIELD_MAP = (
    ("disagreement_claims", "disagreement_claims"),
    ("stage_1_reasoning", "stage_1_reasoning"),
    ("raw_response", "raw_response"),
    ("prompt_version", "prompt_version"),
    ("rubric_version", "rubric_version"),
    ("prompt_tokens", "prompt_tokens"),
    ("completion_tokens", "completion_tokens"),
    ("total_tokens", "total_tokens"),
    ("cost_usd", "cost_usd"),
)

_CACHE_ONLY_FIELDS = (
    "content_hash",
    "evaluation_duration_ms",
)

_CACHED_EVALUATION_FIELDS = tuple(
    dict.fromkeys(
        [target_attr for target_attr, _ in _COMMON_RESULT_FIELD_MAP]
        + [target_attr for target_attr, _ in _EVALUATION_ONLY_FIELD_MAP]
        + list(_CACHE_ONLY_FIELDS)
    )
)


def apply_result_fields(
    target: EvaluationResult | StepEvaluationResult,
    result: dict,
    field_map: tuple[tuple[str, str], ...],
) -> None:
    """Copy selected values from a result dict onto an ORM target object."""
    for target_attr, result_key in field_map:
        setattr(target, target_attr, result.get(result_key))


def apply_result_to_evaluation(evaluation: EvaluationResult, result: dict) -> None:
    """Map a trace-level evaluation result dict onto an `EvaluationResult`."""
    apply_result_fields(evaluation, result, _COMMON_RESULT_FIELD_MAP)
    apply_result_fields(evaluation, result, _EVALUATION_ONLY_FIELD_MAP)


def apply_result_to_step(step_eval: StepEvaluationResult, result: dict) -> None:
    """Map a step-level evaluation result dict onto a `StepEvaluationResult`."""
    apply_result_fields(step_eval, result, _COMMON_RESULT_FIELD_MAP)


def copy_cached_evaluation(source: EvaluationResult, target: EvaluationResult) -> None:
    """Copy cache-relevant evaluation fields from one ORM object to another."""
    for col in _CACHED_EVALUATION_FIELDS:
        setattr(target, col, getattr(source, col))
