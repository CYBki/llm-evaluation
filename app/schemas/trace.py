from datetime import datetime

from pydantic import BaseModel

from app.models.trace import TraceStatus


class ScoresResponse(BaseModel):
    """Numeric metric scores."""

    clarity: float | None = None
    coherence: float | None = None
    helpfulness: float | None = None
    completeness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    faithfulness: float | None = None
    hallucination_score: float | None = None
    citation_check: float | None = None


class FlagsResponse(BaseModel):
    """Boolean quality flags."""

    is_off_topic: bool | None = None
    is_deflection: bool | None = None


class CompletenessKeyPointResponse(BaseModel):
    point: str
    status: str
    evidence: str


class HallucinationClaimResponse(BaseModel):
    context_quote: str
    context_quote_type: str
    answer_quote: str
    reasoning: str
    disagreement_type: str


class DetailsResponse(BaseModel):
    """Detailed claim-level and key-point-level breakdowns."""

    hallucination_claims: list[HallucinationClaimResponse] = []
    completeness_key_points: list[CompletenessKeyPointResponse] = []


class VerdictsResponse(BaseModel):
    """Descriptive verdict labels (2-3 words) per metric."""

    overall_score: str | None = None
    clarity: str | None = None
    coherence: str | None = None
    helpfulness: str | None = None
    completeness: str | None = None
    answer_relevancy: str | None = None
    context_precision: str | None = None
    context_recall: str | None = None
    faithfulness: str | None = None
    hallucination_score: str | None = None
    citation_check: str | None = None


class EvaluationResponse(BaseModel):
    """Clean user-facing evaluation output."""

    overall_score: float | None = None
    confidence: float | None = None
    scores: ScoresResponse
    verdicts: VerdictsResponse | None = None
    flags: FlagsResponse
    reasoning_summary: str | None = None
    details: DetailsResponse
    evaluation_commentary: str | None = None
    evaluation_duration_ms: int | None = None


class EvaluationDetailResponse(EvaluationResponse):
    """Extended evaluation output including internal debug fields."""

    stage_1_reasoning: str | None = None
    disagreement_claims: list[dict] | None = None
    model_used: str | None = None
    prompt_version: str | None = None
    rubric_version: str | None = None


class StepEvaluationResponse(BaseModel):
    """Per-agent-step evaluation result using the same metrics."""

    step_index: int
    agent_name: str
    overall_score: float | None = None
    confidence: float | None = None
    scores: ScoresResponse
    verdicts: VerdictsResponse | None = None
    flags: FlagsResponse
    reasoning_summary: str | None = None
    details: DetailsResponse


class MultiAgentEvaluationResponse(EvaluationResponse):
    """Evaluation response extended with step-level results and pipeline score."""

    pipeline_score: float | None = None
    pipeline_verdict: str | None = None
    step_evaluations: list[StepEvaluationResponse] = []


class MultiAgentEvaluationDetailResponse(EvaluationDetailResponse):
    """Detail response extended with step-level results and pipeline score."""

    pipeline_score: float | None = None
    pipeline_verdict: str | None = None
    step_evaluations: list[StepEvaluationResponse] = []


class TraceResponse(BaseModel):
    id: str
    question: str
    answer: str
    contexts: list[str] | None = None
    metadata: dict | None = None
    status: TraceStatus
    created_at: datetime
    evaluation: MultiAgentEvaluationResponse | EvaluationResponse | None = None


class TraceDetailResponse(BaseModel):
    """Trace with full evaluation debug info (detail=full)."""

    id: str
    question: str
    answer: str
    contexts: list[str] | None = None
    metadata: dict | None = None
    status: TraceStatus
    created_at: datetime
    evaluation: MultiAgentEvaluationDetailResponse | EvaluationDetailResponse | None = (
        None
    )


class TraceListResponse(BaseModel):
    items: list[TraceResponse]
    page: int
    per_page: int
    total: int
