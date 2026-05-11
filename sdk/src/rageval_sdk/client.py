"""
RAG Eval — Lightweight HTTP client for RAG Eval API.

Usage:
    from rageval_sdk import RagEvalClient

    client = RagEvalClient(api_url="http://localhost:8000", api_key="YOUR_KEY")

    # Submit a trace for evaluation
    result = client.ingest(
        question="What is the capital of France?",
        answer="The capital of France is Paris.",
        contexts=["Paris is the capital and largest city of France."],
        ground_truth="Paris",
    )

    # BYOK: use your own LLM API key for evaluation
    result = client.ingest(
        question="What is the capital of France?",
        answer="The capital of France is Paris.",
        llm_api_key="sk-your-openai-key",
    )

    # Check evaluation status
    trace = client.get_trace(result["id"])
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("rageval_sdk")


class RagEvalClient:
    """Synchronous HTTP client for RAG Eval API."""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        *,
        llm_api_key: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.llm_api_key = llm_api_key
        self.timeout = timeout
        headers: dict[str, str] = {"X-API-Key": self.api_key}
        if self.llm_api_key:
            headers["X-LLM-API-Key"] = self.llm_api_key
        self._client = httpx.Client(
            base_url=self.api_url,
            headers=headers,
            timeout=self.timeout,
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> "RagEvalClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ── API Methods ──

    def ingest(
        self,
        question: str,
        answer: str,
        *,
        contexts: list[str] | None = None,
        ground_truth: str | None = None,
        webhook_url: str | None = None,
        metadata: dict[str, Any] | None = None,
        llm_api_key: str | None = None,
    ) -> dict[str, Any]:
        """Submit a trace for evaluation.

        Args:
            question: The user question.
            answer: The LLM-generated answer.
            contexts: Retrieved context passages (for RAG evaluation).
            ground_truth: Expected correct answer (optional).
            webhook_url: URL to receive evaluation results via webhook.
            metadata: Additional metadata (e.g., pipeline steps).
            llm_api_key: BYOK — your own OpenAI/LLM API key for this evaluation.
                Overrides the client-level llm_api_key if set.

        Returns:
            API response dict with trace ID and status.

        Raises:
            httpx.HTTPStatusError: If the API returns an error status code.
        """
        payload: dict[str, Any] = {
            "question": question,
            "answer": answer,
        }
        if contexts is not None:
            payload["contexts"] = contexts
        if ground_truth is not None:
            payload["ground_truth"] = ground_truth
        if webhook_url is not None:
            payload["webhook_url"] = webhook_url
        if metadata is not None:
            payload["metadata"] = metadata

        # Per-request BYOK key overrides client-level key
        headers: dict[str, str] = {}
        key = llm_api_key or self.llm_api_key
        if key:
            headers["X-LLM-API-Key"] = key

        resp = self._client.post("/api/v1/ingest", json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()

    def get_trace(self, trace_id: str) -> dict[str, Any]:
        """Get evaluation results for a trace.

        Args:
            trace_id: The trace ID returned by ingest().

        Returns:
            Trace data including evaluation scores.
        """
        resp = self._client.get(f"/api/v1/traces/{trace_id}")
        resp.raise_for_status()
        return resp.json()

    def list_traces(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List evaluation traces.

        Args:
            limit: Maximum number of traces to return.
            offset: Pagination offset.

        Returns:
            Paginated list of traces.
        """
        resp = self._client.get(
            "/api/v1/traces",
            params={"limit": limit, "offset": offset},
        )
        resp.raise_for_status()
        return resp.json()

    def health(self) -> dict[str, Any]:
        """Check API health status."""
        resp = self._client.get("/health")
        resp.raise_for_status()
        return resp.json()
