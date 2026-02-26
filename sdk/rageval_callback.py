"""
RAG Eval — LangChain Callback Handler

Kullanıcı AgentExecutor'a tek satırda ekler, agent zincirindeki
tüm adımları otomatik yakalar ve bizim API'ye gönderir.

Kullanım:
    from rageval_callback import RagEvalCallback

    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        callbacks=[RagEvalCallback(api_url="http://sunucu:8000", api_key="API_KEY")]
    )
    result = executor.invoke({"input": "soru"})
"""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID

import httpx

try:
    from langchain_core.callbacks import BaseCallbackHandler
except ImportError:
    try:
        from langchain.callbacks.base import BaseCallbackHandler
    except ImportError:
        raise ImportError(
            "langchain veya langchain_core kurulu değil. "
            "pip install langchain-core ile kurun."
        )

logger = logging.getLogger("rageval_callback")


class RagEvalCallback(BaseCallbackHandler):
    """LangChain callback that auto-collects agent steps and sends to RAG Eval API."""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        *,
        timeout: float = 60.0,
        send_on_chain_end: bool = True,
    ) -> None:
        super().__init__()
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.send_on_chain_end = send_on_chain_end

        # ── Per-run state ──
        self._steps: list[dict] = []
        self._step_index: int = 0
        self._current_step_start: float | None = None
        self._current_tool_name: str | None = None
        self._current_tool_input: str | None = None
        self._question: str | None = None
        self._answer: str | None = None
        self._contexts: list[str] | None = None

    # ── Chain start: capture question ──

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        # Top-level chain carries the user question
        if parent_run_id is None:
            self._question = inputs.get("input") or inputs.get("question") or str(inputs)
            self._steps = []
            self._step_index = 0

    # ── Agent action: tool call start ──

    def on_agent_action(self, action: Any, *, run_id: UUID, **kwargs: Any) -> None:
        self._step_index += 1
        self._current_step_start = time.perf_counter()
        self._current_tool_name = getattr(action, "tool", None) or "unknown_tool"
        self._current_tool_input = (
            getattr(action, "tool_input", None) or getattr(action, "log", "")
        )
        if isinstance(self._current_tool_input, dict):
            self._current_tool_input = str(self._current_tool_input)

    # ── Tool end: capture output ──

    def on_tool_end(self, output: str, *, run_id: UUID, **kwargs: Any) -> None:
        latency_ms = None
        if self._current_step_start:
            latency_ms = round((time.perf_counter() - self._current_step_start) * 1000, 1)

        self._steps.append({
            "step_index": self._step_index,
            "agent": self._current_tool_name or f"step_{self._step_index}",
            "input": self._current_tool_input or "",
            "output": str(output) if output else "",
            "latency_ms": latency_ms,
        })

        self._current_tool_name = None
        self._current_tool_input = None
        self._current_step_start = None

    # ── Agent finish: capture final answer ──

    def on_agent_finish(self, finish: Any, *, run_id: UUID, **kwargs: Any) -> None:
        output = getattr(finish, "return_values", {})
        self._answer = output.get("output") or str(output)

    # ── Chain end: send to API ──

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        # Only fire on top-level chain end
        if parent_run_id is not None:
            return
        if not self.send_on_chain_end:
            return

        # Fallback answer
        if not self._answer:
            self._answer = outputs.get("output") or str(outputs)

        self._send_trace()

    # ── Manual send (if send_on_chain_end=False) ──

    def send(
        self,
        question: str | None = None,
        answer: str | None = None,
        contexts: list[str] | None = None,
    ) -> dict | None:
        """Manually send the collected trace. Use when send_on_chain_end=False."""
        if question:
            self._question = question
        if answer:
            self._answer = answer
        if contexts:
            self._contexts = contexts
        return self._send_trace()

    # ── Internal ──

    def _send_trace(self) -> dict | None:
        if not self._question or not self._answer:
            logger.warning("Skipping trace send: question or answer is empty")
            return None

        payload: dict[str, Any] = {
            "question": self._question,
            "answer": self._answer,
        }

        if self._contexts:
            payload["contexts"] = self._contexts

        if self._steps:
            payload["metadata"] = {
                "pipeline_type": "multi-agent",
                "steps": self._steps,
            }

        try:
            resp = httpx.post(
                f"{self.api_url}/api/v1/ingest",
                headers={"X-API-Key": self.api_key},
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            result = resp.json()
            logger.info(
                "Trace sent successfully: id=%s, status=%s, steps=%d",
                result.get("id"),
                result.get("status"),
                len(self._steps),
            )
            return result
        except Exception:
            logger.exception("Failed to send trace to RAG Eval API")
            return None
        finally:
            # Reset state for next run
            self._steps = []
            self._step_index = 0
            self._question = None
            self._answer = None
            self._contexts = None
