from datetime import datetime

from pydantic import BaseModel, Field


class TraceCreate(BaseModel):
    question: str = Field(min_length=1, max_length=50000)
    answer: str = Field(min_length=1, max_length=100000)
    contexts: list[str] | None = None
    ground_truth: str | None = None
    metadata: dict | None = None


class TraceIngestResponse(BaseModel):
    id: str
    status: str
    created_at: datetime


class TraceBatchCreate(BaseModel):
    traces: list[TraceCreate] = Field(min_length=1, max_length=100)


class TraceBatchIngestResponse(BaseModel):
    items: list[TraceIngestResponse]
    count: int


# ── Evaluation Scores (user-facing) ────────────────────────────────────

class ScoresResponse(BaseModel):
    """Numeric metric scores."""
    clarity: float | None = None
    coherence: float | None = None
    helpfulness: float | None = None
    completeness: float | None = None
    answer_relevancy: float | None = None
    faithfulness: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    hallucination_score: float | None = None
    citation_check: float | None = None


class FlagsResponse(BaseModel):
    """Boolean quality flags."""
    is_off_topic: bool | None = None
    is_deflection: bool | None = None


class FaithfulnessClaimResponse(BaseModel):
    claim: str
    verdict: str
    reason: str


class CompletenessKeyPointResponse(BaseModel):
    point: str
    status: str
    evidence: str


class DetailsResponse(BaseModel):
    """Detailed claim-level and key-point-level breakdowns."""
    faithfulness_claims: list[FaithfulnessClaimResponse] = []
    completeness_key_points: list[CompletenessKeyPointResponse] = []


class EvaluationResponse(BaseModel):
    """Clean user-facing evaluation output."""
    overall_score: float | None = None
    confidence: float | None = None
    scores: ScoresResponse
    flags: FlagsResponse
    reasoning_summary: str | None = None
    details: DetailsResponse


class EvaluationDetailResponse(EvaluationResponse):
    """Extended evaluation output including internal debug fields."""
    specificity: float | None = None
    stage_1_reasoning: str | None = None
    disagreement_claims: list[dict] | None = None
    model_used: str | None = None
    prompt_version: str | None = None
    rubric_version: str | None = None


# ── Trace Responses ────────────────────────────────────────────────────

class TraceResponse(BaseModel):
    id: str
    question: str
    answer: str
    contexts: list[str] | None = None
    metadata: dict | None = None
    status: str
    created_at: datetime
    evaluation: EvaluationResponse | None = None


class TraceDetailResponse(BaseModel):
    """Trace with full evaluation debug info (detail=full)."""
    id: str
    question: str
    answer: str
    contexts: list[str] | None = None
    metadata: dict | None = None
    status: str
    created_at: datetime
    evaluation: EvaluationDetailResponse | None = None


class TraceListResponse(BaseModel):
    items: list[TraceResponse]
    page: int
    per_page: int
    total: int
