from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# ── Retry configuration ────────────────────────────────────────────────
_MAX_RETRIES = 3  # total attempts (1 original + 2 retries)
_BACKOFF_BASE = 1.0  # initial wait in seconds
_BACKOFF_FACTOR = 2.0  # multiplier per retry
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 529}

# ── Circuit breaker configuration ──────────────────────────────────────
_CB_FAILURE_THRESHOLD = 5  # consecutive failures to trip the breaker
_CB_RECOVERY_TIMEOUT = 30.0  # seconds in OPEN state before trying HALF_OPEN


class _CBState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class _CircuitBreaker:
    """In-process circuit breaker for LLM API calls.

    State transitions:
        CLOSED  ──[N consecutive failures]──→  OPEN
        OPEN    ──[recovery_timeout elapsed]──→ HALF_OPEN
        HALF_OPEN ──[success]──→ CLOSED
        HALF_OPEN ──[failure]──→ OPEN
    """

    def __init__(
        self,
        failure_threshold: int = _CB_FAILURE_THRESHOLD,
        recovery_timeout: float = _CB_RECOVERY_TIMEOUT,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._state = _CBState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> _CBState:
        """Return effective state (auto-transition OPEN → HALF_OPEN on timeout)."""
        if self._state == _CBState.OPEN:
            if time.monotonic() - self._last_failure_time >= self._recovery_timeout:
                return _CBState.HALF_OPEN
        return self._state

    async def before_call(self) -> None:
        """Check breaker state before making an API call.

        Raises LLMClientError immediately if the circuit is OPEN.
        Uses threading.Lock for cross-event-loop safety (Celery workers
        create a new loop per asyncio.run()).
        """
        with self._lock:
            effective = self.state
            if effective == _CBState.OPEN:
                remaining = self._recovery_timeout - (
                    time.monotonic() - self._last_failure_time
                )
                raise LLMClientError(
                    f"Circuit breaker OPEN – LLM calls disabled for {remaining:.0f}s "
                    f"after {self._failure_threshold} consecutive failures"
                )
            if effective == _CBState.HALF_OPEN:
                logger.info("Circuit breaker HALF_OPEN – allowing probe request")

    async def record_success(self) -> None:
        """Reset failure counter on a successful call."""
        with self._lock:
            if self._state != _CBState.CLOSED or self._failure_count > 0:
                logger.info(
                    "Circuit breaker → CLOSED (was %s, failures reset from %d)",
                    self._state.value,
                    self._failure_count,
                )
            self._failure_count = 0
            self._state = _CBState.CLOSED

    async def record_failure(self) -> None:
        """Increment failure counter; trip breaker if threshold reached."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self._failure_threshold:
                self._state = _CBState.OPEN
                logger.error(
                    "Circuit breaker → OPEN after %d consecutive failures "
                    "(will recover in %.0fs)",
                    self._failure_count,
                    self._recovery_timeout,
                )
            elif self._state == _CBState.HALF_OPEN:
                # Probe failed → back to OPEN
                self._state = _CBState.OPEN
                logger.warning(
                    "Circuit breaker HALF_OPEN probe failed → OPEN "
                    "(will retry in %.0fs)",
                    self._recovery_timeout,
                )
            else:
                logger.warning(
                    "Circuit breaker: failure %d/%d",
                    self._failure_count,
                    self._failure_threshold,
                )


class LLMClientError(Exception):
    pass


@dataclass
class LLMResponse:
    content: str
    raw: dict[str, Any]
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class OpenAILLMClient:
    _clients_by_loop: dict[int, httpx.AsyncClient] = {}
    _clients_lock = threading.Lock()
    _circuit_breaker: _CircuitBreaker = _CircuitBreaker()

    def __init__(self) -> None:
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url.rstrip("/")
        self.timeout_seconds = settings.llm_timeout_seconds
        # Embedding endpoint (may differ from chat endpoint, e.g. when chat
        # is routed through OpenRouter which does not serve embeddings).
        self.embedding_base_url = (
            settings.embedding_base_url or settings.llm_base_url
        ).rstrip("/")
        self.embedding_api_key = (
            settings.embedding_api_key or settings.llm_api_key
        )
        # Per-instance token accumulator
        self._accumulated_prompt_tokens = 0
        self._accumulated_completion_tokens = 0

    @property
    def _is_openrouter(self) -> bool:
        return "openrouter.ai" in self.base_url

    @property
    def is_enabled(self) -> bool:
        return bool(self.api_key)

    # ── Loop-aware connection pool ──────────────────────────────────────

    @classmethod
    def _get_http_client(cls) -> httpx.AsyncClient:
        """Return a httpx.AsyncClient bound to the *current* event loop.

        Each asyncio.run() creates a new event loop. Celery workers call
        asyncio.run() per-task, so a single class-level client would be
        bound to a stale loop on the second task. This method creates one
        client per loop id, automatically replacing stale/closed ones.
        """
        loop = asyncio.get_running_loop()
        loop_id = id(loop)

        with cls._clients_lock:
            client = cls._clients_by_loop.get(loop_id)
            if client is not None and not client.is_closed:
                return client

            # Clean up stale entries (closed clients from dead loops)
            stale = [k for k, v in cls._clients_by_loop.items() if v.is_closed]
            for k in stale:
                del cls._clients_by_loop[k]

            client = httpx.AsyncClient(
                timeout=settings.llm_timeout_seconds,
                limits=httpx.Limits(
                    max_connections=20,
                    max_keepalive_connections=10,
                    keepalive_expiry=30,
                ),
                http2=True,
            )
            cls._clients_by_loop[loop_id] = client
            logger.info(
                "Created httpx.AsyncClient for loop %d (pool: max=20, keepalive=10)",
                loop_id,
            )
            return client

    @classmethod
    async def close_shared_client(cls) -> None:
        """Gracefully close the HTTP client bound to the current event loop."""
        loop = asyncio.get_running_loop()
        loop_id = id(loop)
        with cls._clients_lock:
            client = cls._clients_by_loop.pop(loop_id, None)
        if client is not None and not client.is_closed:
            await client.aclose()
            logger.info("Closed httpx.AsyncClient for loop %d", loop_id)

    # ── Retry wrapper ───────────────────────────────────────────────────

    async def _request_with_retry(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        *,
        label: str = "OpenAI",
    ) -> httpx.Response:
        """POST with exponential backoff retry on transient errors.

        Retries on: 429, 500, 502, 503, 529, and timeouts.
        Respects Retry-After header on 429 responses.
        Non-retryable errors (400, 401, 403, 404) raise immediately.
        Integrates with circuit breaker to skip calls when API is down.
        """
        cb = self._circuit_breaker
        await cb.before_call()  # raises LLMClientError if OPEN

        client = self._get_http_client()
        last_exc: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = await client.post(url, headers=headers, json=payload)

                # Success
                if resp.status_code < 400:
                    await cb.record_success()
                    return resp

                # Non-retryable client errors — don't count toward circuit breaker
                if (
                    resp.status_code < 500
                    and resp.status_code not in _RETRYABLE_STATUS_CODES
                ):
                    raise LLMClientError(
                        f"{label} error {resp.status_code}: {resp.text}"
                    )

                # Retryable error
                if resp.status_code in _RETRYABLE_STATUS_CODES:
                    wait = _BACKOFF_BASE * (_BACKOFF_FACTOR ** (attempt - 1))

                    # Respect Retry-After header (429)
                    retry_after = resp.headers.get("retry-after")
                    if retry_after:
                        try:
                            wait = max(wait, float(retry_after))
                        except (ValueError, TypeError):
                            pass

                    if attempt < _MAX_RETRIES:
                        logger.warning(
                            "%s returned %d (attempt %d/%d), retrying in %.1fs",
                            label,
                            resp.status_code,
                            attempt,
                            _MAX_RETRIES,
                            wait,
                        )
                        await asyncio.sleep(wait)
                        continue

                    # Final attempt exhausted — record failure for circuit breaker
                    await cb.record_failure()
                    raise LLMClientError(
                        f"{label} error {resp.status_code} after {_MAX_RETRIES} attempts: {resp.text}"
                    )

                # Other 5xx not in retryable set — raise immediately
                raise LLMClientError(f"{label} error {resp.status_code}: {resp.text}")

            except httpx.TimeoutException as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    wait = _BACKOFF_BASE * (_BACKOFF_FACTOR ** (attempt - 1))
                    logger.warning(
                        "%s request timed out (attempt %d/%d), retrying in %.1fs",
                        label,
                        attempt,
                        _MAX_RETRIES,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                await cb.record_failure()
                raise LLMClientError(
                    f"{label} request timed out after {_MAX_RETRIES} attempts "
                    f"({self.timeout_seconds}s each)"
                ) from exc

            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    wait = _BACKOFF_BASE * (_BACKOFF_FACTOR ** (attempt - 1))
                    logger.warning(
                        "%s HTTP error (attempt %d/%d): %s, retrying in %.1fs",
                        label,
                        attempt,
                        _MAX_RETRIES,
                        exc,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                await cb.record_failure()
                raise LLMClientError(
                    f"{label} HTTP error after {_MAX_RETRIES} attempts: {exc}"
                ) from exc

        # Should not reach here, but just in case
        await cb.record_failure()
        raise LLMClientError(
            f"{label} failed after {_MAX_RETRIES} attempts"
        ) from last_exc

    async def create_embeddings(
        self,
        *,
        texts: list[str],
        model: str = "text-embedding-3-small",
    ) -> list[list[float]]:
        """Return embedding vectors for each text using OpenAI Embeddings API."""
        if not self.embedding_api_key:
            raise LLMClientError(
                "No embedding API key configured "
                "(set EMBEDDING_API_KEY or LLM_API_KEY)"
            )

        url = f"{self.embedding_base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.embedding_api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": model, "input": texts}

        resp = await self._request_with_retry(
            url, headers, payload, label="LLM Embeddings"
        )

        data = resp.json()
        try:
            # Sort by index to guarantee order matches input order
            sorted_data = sorted(data["data"], key=lambda x: x["index"])
            return [item["embedding"] for item in sorted_data]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError("Invalid LLM Embeddings response format") from exc

    async def chat_completion(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_completion_tokens: int = 512,
        response_format_json: bool = False,
        json_schema: dict | None = None,
    ) -> LLMResponse:
        if not self.api_key:
            raise LLMClientError("LLM_API_KEY not configured")

        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "max_completion_tokens": max_completion_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if json_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": json_schema,
            }
        elif response_format_json:
            payload["response_format"] = {"type": "json_object"}

        # OpenRouter: pin to providers that support response_format/json_schema.
        # Ignored by native OpenAI API (would 400); only attached when base_url
        # is OpenRouter.
        if self._is_openrouter:
            order = [
                p.strip()
                for p in settings.openrouter_provider_order.split(",")
                if p.strip()
            ]
            provider_cfg: dict[str, Any] = {
                "require_parameters": settings.openrouter_require_parameters,
            }
            if order:
                provider_cfg["order"] = order
            payload["provider"] = provider_cfg

        resp = await self._request_with_retry(
            url, headers, payload, label="LLM Chat"
        )

        data = resp.json()
        try:
            message = data["choices"][0]["message"]
            content = message.get("content")
            refusal = message.get("refusal")
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError("Invalid LLM response format") from exc

        if refusal:
            raise LLMClientError(f"LLM refused the request: {refusal}")

        # Handle content=None (can happen with some structured output responses)
        if content is None:
            content = ""

        # Check for truncated output
        finish_reason = data.get("choices", [{}])[0].get("finish_reason", "")
        if finish_reason == "length":
            logger.warning(
                "LLM response truncated (finish_reason=length) for model=%s",
                payload.get("model", "unknown"),
            )

        # ── Extract token usage ──
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)

        # Accumulate on instance
        self._accumulated_prompt_tokens += prompt_tokens
        self._accumulated_completion_tokens += completion_tokens

        return LLMResponse(
            content=content,
            raw=data,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
