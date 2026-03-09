from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


class TraceCreate(BaseModel):
    question: str = Field(min_length=1, max_length=50000)
    answer: str = Field(min_length=1, max_length=100000)
    contexts: list[str] | None = None
    ground_truth: str | None = None
    metadata: dict | None = None
    webhook_url: str | None = Field(
        default=None,
        max_length=2048,
        description="URL to receive POST callback when evaluation completes",
    )

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        parsed = urlparse(v)
        if parsed.scheme != "https":
            raise ValueError("webhook_url must use https:// scheme")
        if not parsed.hostname:
            raise ValueError("webhook_url must contain a valid hostname")
        # Reject bare IPs (require FQDN with at least one dot)
        hostname = parsed.hostname
        if hostname.replace(".", "").isdigit() or ":" in hostname:
            raise ValueError("webhook_url must use a domain name, not an IP address")
        if "." not in hostname:
            raise ValueError("webhook_url must be a fully qualified domain name")
        return v


class TraceIngestResponse(BaseModel):
    id: str
    status: str
    created_at: datetime


class TraceBatchCreate(BaseModel):
    traces: list[TraceCreate] = Field(min_length=1, max_length=100)
    webhook_url: str | None = Field(
        default=None,
        max_length=2048,
        description="Batch-level webhook URL. Applied to all traces that don't have their own webhook_url.",
    )

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        parsed = urlparse(v)
        if parsed.scheme != "https":
            raise ValueError("webhook_url must use https:// scheme")
        if not parsed.hostname:
            raise ValueError("webhook_url must contain a valid hostname")
        hostname = parsed.hostname
        if hostname.replace(".", "").isdigit() or ":" in hostname:
            raise ValueError("webhook_url must use a domain name, not an IP address")
        if "." not in hostname:
            raise ValueError("webhook_url must be a fully qualified domain name")
        return v


class TraceBatchIngestResponse(BaseModel):
    items: list[TraceIngestResponse]
    count: int
