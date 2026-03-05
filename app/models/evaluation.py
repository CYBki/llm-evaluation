import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("traces.id"), nullable=False, unique=True, index=True)

    clarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    specificity: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_off_topic: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    completeness: Mapped[float | None] = mapped_column(Float, nullable=True)
    coherence: Mapped[float | None] = mapped_column(Float, nullable=True)
    helpfulness: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_deflection: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    evaluation_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasoning_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    disagreement_claims: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    stage_1_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)

    # ── RAG-specific metrics ──
    answer_relevancy: Mapped[float | None] = mapped_column(Float, nullable=True)
    faithfulness: Mapped[float | None] = mapped_column(Float, nullable=True)
    hallucination_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    citation_check: Mapped[float | None] = mapped_column(Float, nullable=True)
    faithfulness_claims: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    hallucination_claims: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    completeness_key_points: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)

    # ── Context retrieval quality metrics ──
    context_precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    context_recall: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Multi-agent pipeline score ──
    pipeline_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Content-based cache key ──
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # ── Token usage & cost tracking ──
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    evaluated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    model_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rubric_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    trace = relationship("Trace", back_populates="evaluation_result")


class StepEvaluationResult(Base):
    """Per-agent-step evaluation using the same metrics as trace-level."""
    __tablename__ = "step_evaluation_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("traces.id"), nullable=False, index=True)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    agent_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # ── Same metrics as trace-level ──
    clarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    specificity: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_off_topic: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    completeness: Mapped[float | None] = mapped_column(Float, nullable=True)
    coherence: Mapped[float | None] = mapped_column(Float, nullable=True)
    helpfulness: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_deflection: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    evaluation_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasoning_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── RAG-specific metrics ──
    answer_relevancy: Mapped[float | None] = mapped_column(Float, nullable=True)
    faithfulness: Mapped[float | None] = mapped_column(Float, nullable=True)
    hallucination_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    citation_check: Mapped[float | None] = mapped_column(Float, nullable=True)
    faithfulness_claims: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    hallucination_claims: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    completeness_key_points: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)

    # ── Context retrieval quality metrics ──
    context_precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    context_recall: Mapped[float | None] = mapped_column(Float, nullable=True)

    evaluated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    model_used: Mapped[str | None] = mapped_column(String(50), nullable=True)

    trace = relationship("Trace", back_populates="step_evaluation_results")
