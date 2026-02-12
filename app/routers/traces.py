from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.trace import Trace
from app.models.user import User
from app.schemas.ingest import TraceListResponse, TraceResponse
from app.services.ingest_service import get_trace_by_id, list_traces

router = APIRouter()


def _to_trace_response(trace: Trace) -> TraceResponse:
    return TraceResponse(
        id=str(trace.id),
        question=trace.question,
        answer=trace.answer,
        contexts=trace.contexts,
        metadata=trace.meta,
        status=trace.status,
        created_at=trace.created_at,
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
    trace = get_trace_by_id(db, current_user, trace_id)
    if not trace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found")
    return _to_trace_response(trace)
