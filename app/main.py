import logging
import sys
import time
import traceback
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.models import APIKey, APIKeyIn
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text

from app.database import SessionLocal
from app.exceptions import AppError
from app.routers.auth import router as auth_router
from app.routers.ingest import router as ingest_router
from app.routers.metrics import router as metrics_router
from app.routers.traces import router as traces_router

# ── Structured JSON logging ──────────────────────────────────────────────

try:
    import json as _json

    class _JSONFormatter(logging.Formatter):
        """Emit log records as single-line JSON objects (ELK / Datadog ready)."""

        def format(self, record: logging.LogRecord) -> str:
            log_obj = {
                "timestamp": self.formatTime(record, self.datefmt),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            if hasattr(record, "request_id"):
                log_obj["request_id"] = record.request_id
            if record.exc_info and record.exc_info[0] is not None:
                log_obj["exception"] = self.formatException(record.exc_info)
            return _json.dumps(log_obj, ensure_ascii=False)

    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(_JSONFormatter())
    logging.root.handlers = [_handler]
    logging.root.setLevel(logging.INFO)
except Exception:
    # Fallback to basic logging if JSON formatter fails
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

logger = logging.getLogger(__name__)

# ── App setup ────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

_API_DESCRIPTION = """\
**RAG Eval API** — RAG (Retrieval-Augmented Generation) sistemlerinin cevap kalitesini
otomatik olarak ölçen değerlendirme platformu.

### Özellikler
- **Two-stage LLM-as-Judge:** gpt-5.2 (CoT reasoning) + gpt-5-mini (JSON scoring)
- **13 metrik:** clarity, coherence, helpfulness, completeness, answer_relevancy,
  hallucination_score, context_precision, context_recall, citation_check, specificity,
  is_off_topic, is_deflection, overall_score
- **Async evaluation:** Redis + Celery ile arka plan değerlendirme
- **Score caps:** off-topic ≤ 0.20, deflection ≤ 0.20, contradiction ≤ 0.35

### Kimlik Doğrulama
Tüm endpoint'ler (auth hariç) `X-API-Key` header'ı gerektirir.
`POST /api/v1/auth/register` ile kayıt olup API key alabilirsiniz.
"""

app = FastAPI(
    title="RAG Eval API",
    description=_API_DESCRIPTION,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "auth",
            "description": "Kullanıcı kaydı ve kimlik doğrulama işlemleri",
        },
        {
            "name": "ingest",
            "description": "Trace gönderme (tek veya toplu). Gönderilen trace'ler otomatik olarak değerlendirilir.",
        },
        {
            "name": "traces",
            "description": "Trace listeleme ve detay görüntüleme. Evaluation sonuçları burada döner.",
        },
        {
            "name": "metrics",
            "description": "Metrik tanımları, açıklamaları ve threshold bilgileri.",
        },
        {
            "name": "health",
            "description": "Sistem sağlık kontrolü",
        },
    ],
    swagger_ui_parameters={"persistAuthorization": True},
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Standardized error handling ──────────────────────────────────────────


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Catch domain exceptions and return a structured JSON error."""
    return JSONResponse(
        status_code=400,
        content={
            "error": type(exc).__name__,
            "detail": str(exc),
            "request_id": getattr(request.state, "request_id", None),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions — never leak raw 500 tracebacks."""
    request_id = getattr(request.state, "request_id", None)
    logger.error(
        "Unhandled exception: %s | request_id=%s",
        exc,
        request_id,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "detail": "An unexpected error occurred. Please try again or contact support.",
            "request_id": request_id,
        },
    )


# ── Request-ID & access-log middleware ───────────────────────────────────


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """Inject request_id into every request and log access info."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id

    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)

    logger.info(
        "%s %s → %s (%.1f ms) [request_id=%s]",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        request_id,
    )
    response.headers["X-Request-ID"] = request_id
    return response


# ── Routers ──────────────────────────────────────────────────────────────

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(ingest_router, prefix="/api/v1/ingest", tags=["ingest"])
app.include_router(traces_router, prefix="/api/v1/traces", tags=["traces"])
app.include_router(metrics_router, prefix="/api/v1/metrics", tags=["metrics"])


@app.get("/health", tags=["health"], summary="Sistem sağlık kontrolü", description="API ve veritabanı durumunu kontrol eder.")
def health() -> dict:
    """API ve PostgreSQL bağlantı durumunu döner."""
    status_detail = {"api": "ok"}
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        status_detail["database"] = "ok"
    except Exception:
        status_detail["database"] = "unavailable"
    return {"status": "ok" if status_detail.get("database") == "ok" else "degraded", "details": status_detail}
