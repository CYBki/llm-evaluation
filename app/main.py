from fastapi import FastAPI

from app.routers.auth import router as auth_router
from app.routers.ingest import router as ingest_router
from app.routers.traces import router as traces_router

app = FastAPI(title="RAG Eval API")

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(ingest_router, prefix="/api/v1/ingest", tags=["ingest"])
app.include_router(traces_router, prefix="/api/v1/traces", tags=["traces"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
