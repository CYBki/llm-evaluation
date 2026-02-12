from datetime import datetime

from pydantic import BaseModel, Field


class TraceCreate(BaseModel):
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    contexts: list[str] = Field(default_factory=list)
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


class TraceResponse(BaseModel):
    id: str
    question: str
    answer: str
    contexts: list[str] | None = None
    metadata: dict | None = None
    status: str
    created_at: datetime


class TraceListResponse(BaseModel):
    items: list[TraceResponse]
    page: int
    per_page: int
    total: int
