from __future__ import annotations

from typing import Protocol

from app.evaluation.llm_client import LLMResponse


class LLMChatClient(Protocol):
    """Behavioral contract for evaluation-time LLM clients."""

    @property
    def is_enabled(self) -> bool: ...

    async def chat_completion(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_completion_tokens: int = 512,
        response_format_json: bool = False,
        json_schema: dict | None = None,
    ) -> LLMResponse: ...
