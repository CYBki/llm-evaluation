from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.trace import Trace
from app.models.user import User
from app.schemas.ingest import EvaluationResponse, TraceListResponse, TraceResponse
from app.services.ingest_service import get_trace_by_id, list_traces

router = APIRouter()


def _to_trace_response(trace: Trace) -> TraceResponse:
    evaluation = trace.evaluation_result
    return TraceResponse(
        id=str(trace.id),
        question=trace.question,
        answer=trace.answer,
        contexts=trace.contexts,
        metadata=trace.meta,
        status=trace.status,
        created_at=trace.created_at,
        evaluation=(
            EvaluationResponse(
                clarity=evaluation.clarity,
                specificity=evaluation.specificity,
                is_off_topic=evaluation.is_off_topic,
                completeness=evaluation.completeness,
                coherence=evaluation.coherence,
                helpfulness=evaluation.helpfulness,
                is_deflection=evaluation.is_deflection,
                overall_score=evaluation.overall_score,
                evaluation_confidence=evaluation.evaluation_confidence,
                reasoning_summary=evaluation.reasoning_summary,
                disagreement_claims=evaluation.disagreement_claims,
                stage_1_reasoning=evaluation.stage_1_reasoning,
                model_used=evaluation.model_used,
                prompt_version=evaluation.prompt_version,
                rubric_version=evaluation.rubric_version,
            )
            if evaluation
            else None
        ),
    )


@router.get("", response_model=TraceListResponse)
def get_traces(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TraceListResponse:
    traces, total = list_traces(db, current_user, page, per_page)
    items = [_to_trace_response(trace) for trace in traces]
    return TraceListResponse(items=items, page=page, per_page=per_page, total=total)


@router.get("/{trace_id}", response_model=TraceResponse)
def get_trace(
    trace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TraceResponse:
    try:
        UUID(trace_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid trace ID format")
    trace = get_trace_by_id(db, current_user, trace_id)
    if not trace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found")
    return _to_trace_response(trace)
