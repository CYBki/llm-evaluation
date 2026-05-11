"""
OpenAI-compatible LLM client with retry, circuit breaker, and connection pooling.

Standalone version — no server dependencies. Configuration is passed via EvalConfig.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

from rageval_sdk._config import EvalConfig

logger = logging.getLogger(__name__)

# ── Retry configuration ────────────────────────────────────────────────
_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0
_BACKOFF_FACTOR = 2.0
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 529}

# ── Circuit breaker configuration ──────────────────────────────────────
_CB_FAILURE_THRESHOLD = 5
_CB_RECOVERY_TIMEOUT = 30.0


class _CBState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class _CircuitBreaker:
    """In-process circuit breaker for LLM API calls."""

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
        if self._state == _CBState.OPEN:
            if time.monotonic() - self._last_failure_time >= self._recovery_timeout:
                return _CBState.HALF_OPEN
        return self._state

    async def before_call(self) -> None:
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


def _extract_openrouter_metadata(
    resp: httpx.Response, payload: dict[str, Any], data: dict[str, Any]
) -> dict[str, Any]:
    provider_headers = {
        key: value
        for key, value in resp.headers.items()
        if "provider" in key.lower() or key.lower().startswith("x-openrouter")
    }
    provider_fields = {
        key: data.get(key)
        for key in (
            "provider",
            "provider_name",
            "provider_id",
            "route",
            "id",
            "model",
        )
        if data.get(key) is not None
    }
    choices = data.get("choices")
    choice = choices[0] if isinstance(choices, list) and choices else {}
    if isinstance(choice, dict):
        for key in ("provider", "provider_name", "provider_id"):
            if choice.get(key) is not None:
                provider_fields[f"choice_{key}"] = choice.get(key)
    return {
        "provider_request": payload.get("provider"),
        "response_headers": provider_headers,
        "response_fields": provider_fields,
    }


class OpenAILLMClient:
    """Async OpenAI-compatible LLM client with retry and circuit breaker."""

    _clients_by_loop: dict[int, httpx.AsyncClient] = {}
    _clients_lock = threading.Lock()
    _circuit_breaker: _CircuitBreaker = _CircuitBreaker()

    def __init__(self, config: EvalConfig) -> None:
        self.api_key = config.api_key
        self.base_url = config.base_url.rstrip("/")
        self.timeout_seconds = config.timeout_seconds
        self._config = config
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
    def _get_http_client(cls, timeout: float = 120.0) -> httpx.AsyncClient:
        loop = asyncio.get_running_loop()
        loop_id = id(loop)

        with cls._clients_lock:
            client = cls._clients_by_loop.get(loop_id)
            if client is not None and not client.is_closed:
                return client

            stale = [k for k, v in cls._clients_by_loop.items() if v.is_closed]
            for k in stale:
                del cls._clients_by_loop[k]

            client = httpx.AsyncClient(
                timeout=timeout,
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
        cb = self._circuit_breaker
        await cb.before_call()

        client = self._get_http_client(self.timeout_seconds)
        last_exc: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = await client.post(url, headers=headers, json=payload)

                if resp.status_code < 400:
                    await cb.record_success()
                    return resp

                if (
                    resp.status_code < 500
                    and resp.status_code not in _RETRYABLE_STATUS_CODES
                ):
                    raise LLMClientError(
                        f"{label} error {resp.status_code}: {resp.text}"
                    )

                if resp.status_code in _RETRYABLE_STATUS_CODES:
                    wait = _BACKOFF_BASE * (_BACKOFF_FACTOR ** (attempt - 1))

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

                    await cb.record_failure()
                    raise LLMClientError(
                        f"{label} error {resp.status_code} after {_MAX_RETRIES} attempts: {resp.text}"
                    )

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

        await cb.record_failure()
        raise LLMClientError(
            f"{label} failed after {_MAX_RETRIES} attempts"
        ) from last_exc

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
            raise LLMClientError("API key not configured")

        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        token_param = (
            "max_completion_tokens"
            if "api.openai.com" in (self.base_url or "")
            else "max_tokens"
        )
        payload: dict[str, Any] = {
            "model": model,
            token_param: max_completion_tokens,
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

        if self._is_openrouter:
            order = [
                p.strip()
                for p in self._config.openrouter_provider_order.split(",")
                if p.strip()
            ]
            provider_cfg: dict[str, Any] = {
                "allow_fallbacks": self._config.openrouter_allow_fallbacks,
                "require_parameters": self._config.openrouter_require_parameters,
            }
            if order:
                provider_cfg["order"] = order
            payload["provider"] = provider_cfg

        resp = await self._request_with_retry(
            url, headers, payload, label="LLM Chat"
        )

        data = resp.json()
        if self._is_openrouter:
            data["_openrouter"] = _extract_openrouter_metadata(resp, payload, data)
            logger.info(
                "OpenRouter provider metadata model=%s metadata=%s",
                model,
                data["_openrouter"],
            )
        try:
            message = data["choices"][0]["message"]
            content = message.get("content")
            refusal = message.get("refusal")
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError("Invalid LLM response format") from exc

        if refusal:
            raise LLMClientError(f"LLM refused the request: {refusal}")

        if content is None:
            content = ""

        finish_reason = data.get("choices", [{}])[0].get("finish_reason", "")
        if finish_reason == "length":
            logger.warning(
                "LLM response truncated (finish_reason=length) for model=%s",
                payload.get("model", "unknown"),
            )

        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)

        self._accumulated_prompt_tokens += prompt_tokens
        self._accumulated_completion_tokens += completion_tokens

        return LLMResponse(
            content=content,
            raw=data,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
