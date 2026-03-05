from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.ingest import (
    TraceBatchCreate,
    TraceBatchIngestResponse,
    TraceCreate,
    TraceIngestResponse,
)
from app.services.ingest_service import create_trace, create_traces_batch

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.post(
    "",
    response_model=TraceIngestResponse,
    summary="Tek trace gönder",
    description="Bir soru-cevap-context trace'i gönderir. Trace otomatik olarak değerlendirilir (sync veya async moda göre).",
    responses={
        200: {"description": "Trace başarıyla alındı, evaluation başlatıldı"},
        401: {"description": "Geçersiz veya eksik API key"},
        422: {"description": "Geçersiz istek (validation hatası)"},
        429: {"description": "Rate limit aşıldı (30/dakika)"},
    },
)
@limiter.limit("30/minute")
def ingest(
    request: Request,
    payload: TraceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TraceIngestResponse:
    """Tek bir trace alır, DB'ye kaydeder ve LLM evaluation'ı tetikler."""
    trace = create_trace(db, current_user, payload)
    return TraceIngestResponse(
        id=str(trace.id), status=trace.status, created_at=trace.created_at
    )


@router.post(
    "/batch",
    response_model=TraceBatchIngestResponse,
    summary="Toplu trace gönder",
    description="Birden fazla trace'i tek istekle gönderir. Her trace bağımsız olarak değerlendirilir.",
    responses={
        200: {"description": "Trace'ler başarıyla alındı"},
        401: {"description": "Geçersiz veya eksik API key"},
        422: {"description": "Geçersiz istek (validation hatası)"},
        429: {"description": "Rate limit aşıldı (10/dakika)"},
    },
)
@limiter.limit("10/minute")
def ingest_batch(
    request: Request,
    payload: TraceBatchCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TraceBatchIngestResponse:
    """Toplu trace alır ve her birini bağımsız olarak değerlendirir."""
    traces = create_traces_batch(db, current_user, payload.traces)
    items = [
        TraceIngestResponse(
            id=str(trace.id), status=trace.status, created_at=trace.created_at
        )
        for trace in traces
    ]
    return TraceBatchIngestResponse(items=items, count=len(items))
