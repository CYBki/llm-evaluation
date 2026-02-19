from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings


class LLMClientError(Exception):
    pass


@dataclass
class LLMResponse:
    content: str
    raw: dict[str, Any]


class OpenAILLMClient:
    def __init__(self) -> None:
        self.api_key = settings.openai_api_key
        self.base_url = settings.openai_base_url.rstrip("/")
        self.timeout_seconds = settings.openai_timeout_seconds

    @property
    def is_enabled(self) -> bool:
        return bool(self.api_key)

    async def create_embeddings(
        self,
        *,
        texts: list[str],
        model: str = "text-embedding-3-small",
    ) -> list[list[float]]:
        """Return embedding vectors for each text using OpenAI Embeddings API."""
        if not self.api_key:
            raise LLMClientError("OPENAI_API_KEY not configured")

        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": model, "input": texts}

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise LLMClientError(f"OpenAI Embeddings request timed out after {self.timeout_seconds}s") from exc
        except httpx.HTTPError as exc:
            raise LLMClientError(f"OpenAI Embeddings HTTP error: {exc}") from exc

        if resp.status_code >= 400:
            raise LLMClientError(f"OpenAI Embeddings error {resp.status_code}: {resp.text}")

        data = resp.json()
        try:
            # Sort by index to guarantee order matches input order
            sorted_data = sorted(data["data"], key=lambda x: x["index"])
            return [item["embedding"] for item in sorted_data]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError("Invalid OpenAI Embeddings response format") from exc

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
            raise LLMClientError("OPENAI_API_KEY not configured")

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

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise LLMClientError(f"OpenAI request timed out after {self.timeout_seconds}s") from exc
        except httpx.HTTPError as exc:
            raise LLMClientError(f"OpenAI HTTP error: {exc}") from exc

        if resp.status_code >= 400:
            raise LLMClientError(f"OpenAI error {resp.status_code}: {resp.text}")

        data = resp.json()
        try:
            message = data["choices"][0]["message"]
            content = message.get("content")
            refusal = message.get("refusal")
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError("Invalid OpenAI response format") from exc

        if refusal:
            raise LLMClientError(f"OpenAI refused the request: {refusal}")

        # Handle content=None (can happen with some structured output responses)
        if content is None:
            content = ""

        # Check for truncated output
        finish_reason = data.get("choices", [{}])[0].get("finish_reason", "")
        if finish_reason == "length":
            import logging
            logging.getLogger(__name__).warning(
                "OpenAI response truncated (finish_reason=length) for model=%s",
                payload.get("model", "unknown"),
            )

        return LLMResponse(content=content, raw=data)
