from datetime import datetime

from pydantic import BaseModel, Field


class TraceCreate(BaseModel):
    question: str = Field(min_length=1, max_length=50000)
    answer: str = Field(min_length=1, max_length=100000)
    contexts: list[str] | None = None
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


class EvaluationResponse(BaseModel):
    clarity: float | None = None
    specificity: float | None = None
    is_off_topic: bool | None = None
    completeness: float | None = None
    coherence: float | None = None
    helpfulness: float | None = None
    is_deflection: bool | None = None
    overall_score: float | None = None
    evaluation_confidence: float | None = None
    reasoning_summary: str | None = None
    disagreement_claims: list[dict] | None = None
    stage_1_reasoning: str | None = None
    model_used: str | None = None
    prompt_version: str | None = None
    rubric_version: str | None = None
    answer_relevancy: float | None = None
    faithfulness: float | None = None
    hallucination_score: float | None = None
    citation_check: float | None = None
    faithfulness_claims: list[dict] | None = None
    completeness_key_points: list[dict] | None = None


class TraceResponse(BaseModel):
    id: str
    question: str
    answer: str
    contexts: list[str] | None = None
    metadata: dict | None = None
    status: str
    created_at: datetime
    evaluation: EvaluationResponse | None = None


class TraceListResponse(BaseModel):
    items: list[TraceResponse]
    page: int
    per_page: int
    total: int
