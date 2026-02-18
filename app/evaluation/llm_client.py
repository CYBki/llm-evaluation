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

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(url, headers=headers, json=payload)

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

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(url, headers=headers, json=payload)

        if resp.status_code >= 400:
            raise LLMClientError(f"OpenAI error {resp.status_code}: {resp.text}")

        data = resp.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError("Invalid OpenAI response format") from exc

        return LLMResponse(content=content, raw=data)
