import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text

from app.database import SessionLocal
from app.routers.auth import router as auth_router
from app.routers.ingest import router as ingest_router
from app.routers.traces import router as traces_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

app = FastAPI(title="RAG Eval API", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app = FastAPI(title="RAG Eval API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(ingest_router, prefix="/api/v1/ingest", tags=["ingest"])
app.include_router(traces_router, prefix="/api/v1/traces", tags=["traces"])


@app.get("/health")
def health() -> dict:
    status_detail = {"api": "ok"}
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        status_detail["database"] = "ok"
    except Exception:
        status_detail["database"] = "unavailable"
    return {"status": "ok" if status_detail.get("database") == "ok" else "degraded", "details": status_detail}
