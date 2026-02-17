from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.ingest import TraceBatchCreate, TraceBatchIngestResponse, TraceCreate, TraceIngestResponse
from app.services.ingest_service import create_trace, create_traces_batch

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.post("", response_model=TraceIngestResponse)
@limiter.limit("30/minute")
def ingest(
    request: Request,
    payload: TraceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TraceIngestResponse:
    trace = create_trace(db, current_user, payload)
    return TraceIngestResponse(id=str(trace.id), status=trace.status, created_at=trace.created_at)


@router.post("/batch", response_model=TraceBatchIngestResponse)
@limiter.limit("10/minute")
def ingest_batch(
    request: Request,
    payload: TraceBatchCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TraceBatchIngestResponse:
    traces = create_traces_batch(db, current_user, payload.traces)
    items = [TraceIngestResponse(id=str(trace.id), status=trace.status, created_at=trace.created_at) for trace in traces]
    return TraceBatchIngestResponse(items=items, count=len(items))
