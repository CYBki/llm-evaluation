"""
Background evaluation engine.

RagEvaluator runs evaluations in background threads so the main
RAG pipeline is never blocked. Supports single and batch submissions.

Usage:
    evaluator = RagEvaluator(api_key="sk-...")

    # Non-blocking: submit and continue
    evaluator.submit(question="...", answer="...", contexts=[...])

    # Batch submit
    evaluator.submit_batch([
        {"question": "Q1", "answer": "A1", "contexts": ["C1"]},
        {"question": "Q2", "answer": "A2", "contexts": ["C2"]},
    ])

    # Get completed results
    completed = evaluator.results

    # Wait for all pending evaluations
    all_results = evaluator.wait()

    # Cleanup
    evaluator.shutdown()
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from rageval_sdk._config import EvalConfig
from rageval_sdk._evaluator import evaluate_trace

logger = logging.getLogger(__name__)


@dataclass
class EvalJob:
    """A single evaluation job."""

    id: str
    question: str
    answer: str
    contexts: list[str] | None = None
    ground_truth: str | None = None
    future: Future | None = field(default=None, repr=False)
    result: dict[str, Any] | None = field(default=None, repr=False)
    error: str | None = None


class RagEvaluator:
    """Background RAG evaluation engine.

    Runs evaluations in background threads so your RAG pipeline
    is never blocked. Collects results asynchronously.

    Args:
        api_key: Your OpenAI API key.
        config: Full EvalConfig (overrides api_key if both given).
        max_workers: Max concurrent background evaluations.
        **config_overrides: Additional EvalConfig fields.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        config: EvalConfig | None = None,
        max_workers: int = 4,
        **config_overrides: Any,
    ) -> None:
        if config is not None:
            self._config = config
        elif api_key:
            self._config = EvalConfig(api_key=api_key, **config_overrides)
        else:
            raise ValueError(
                "Either api_key or config must be provided. "
                "Example: RagEvaluator(api_key='sk-...')"
            )

        self._max_workers = max_workers
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="rageval",
        )
        self._jobs: dict[str, EvalJob] = {}
        self._lock = threading.Lock()
        self._closed = False

        logger.info(
            "RagEvaluator initialized (max_workers=%d, model=%s)",
            max_workers,
            self._config.stage_1_model,
        )

    # ── Submit (non-blocking) ─────────────────────────────────────────

    def submit(
        self,
        question: str,
        answer: str,
        contexts: list[str] | None = None,
        ground_truth: str | None = None,
        *,
        job_id: str | None = None,
    ) -> str:
        """Submit a single evaluation to run in the background.

        Returns immediately with a job ID. The evaluation runs
        in a background thread.

        Args:
            question: The user question.
            answer: The LLM-generated answer.
            contexts: Retrieved context passages.
            ground_truth: Expected correct answer.
            job_id: Optional custom job ID.

        Returns:
            Job ID string (use to retrieve results later).
        """
        if self._closed:
            raise RuntimeError("RagEvaluator is shut down")

        jid = job_id or str(uuid.uuid4())[:8]
        job = EvalJob(
            id=jid,
            question=question,
            answer=answer,
            contexts=contexts,
            ground_truth=ground_truth,
        )

        future = self._executor.submit(self._run_eval, job)
        job.future = future

        with self._lock:
            self._jobs[jid] = job

        logger.info("Submitted evaluation job %s (pending: %d)", jid, self.pending_count)
        return jid

    def submit_batch(
        self,
        traces: list[dict[str, Any]],
    ) -> list[str]:
        """Submit multiple evaluations to run in the background.

        Args:
            traces: List of dicts, each with keys:
                - question (str, required)
                - answer (str, required)
                - contexts (list[str], optional)
                - ground_truth (str, optional)

        Returns:
            List of job IDs.
        """
        job_ids = []
        for i, trace in enumerate(traces):
            if "question" not in trace or "answer" not in trace:
                raise ValueError(
                    f"Trace {i} missing required keys 'question' and 'answer'"
                )
            jid = self.submit(
                question=trace["question"],
                answer=trace["answer"],
                contexts=trace.get("contexts"),
                ground_truth=trace.get("ground_truth"),
            )
            job_ids.append(jid)

        logger.info(
            "Submitted batch of %d evaluations (total pending: %d)",
            len(traces),
            self.pending_count,
        )
        return job_ids

    # ── Results ───────────────────────────────────────────────────────

    @property
    def results(self) -> list[dict[str, Any]]:
        """Return all completed evaluation results (non-blocking)."""
        completed = []
        with self._lock:
            for job in self._jobs.values():
                if job.result is not None:
                    result = dict(job.result)
                    result["_job_id"] = job.id
                    completed.append(result)
        return completed

    @property
    def pending_count(self) -> int:
        """Number of evaluations still running."""
        with self._lock:
            return sum(
                1
                for job in self._jobs.values()
                if job.future is not None and not job.future.done()
            )

    @property
    def completed_count(self) -> int:
        """Number of completed evaluations."""
        with self._lock:
            return sum(1 for job in self._jobs.values() if job.result is not None)

    def get_result(self, job_id: str) -> dict[str, Any] | None:
        """Get the result for a specific job (None if not done yet)."""
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            return None
        if job.result is not None:
            result = dict(job.result)
            result["_job_id"] = job.id
            return result
        return None

    def wait(self, timeout: float | None = None) -> list[dict[str, Any]]:
        """Wait for all pending evaluations to complete.

        Args:
            timeout: Max seconds to wait. None = wait forever.

        Returns:
            List of all evaluation results.
        """
        with self._lock:
            futures = [
                (job.id, job.future)
                for job in self._jobs.values()
                if job.future is not None and not job.future.done()
            ]

        for jid, future in futures:
            try:
                future.result(timeout=timeout)
            except Exception as exc:
                logger.error("Job %s failed: %s", jid, exc)

        return self.results

    # ── Synchronous batch ─────────────────────────────────────────────

    def evaluate_batch(
        self,
        traces: list[dict[str, Any]],
        *,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        """Submit a batch and wait for all results.

        Convenience method that combines submit_batch() + wait().

        Args:
            traces: List of trace dicts (same format as submit_batch).
            timeout: Max seconds to wait per evaluation.

        Returns:
            List of evaluation results in the same order as input.
        """
        job_ids = self.submit_batch(traces)

        # Wait for all to complete
        results_map: dict[str, dict[str, Any]] = {}
        with self._lock:
            jobs = [(jid, self._jobs[jid]) for jid in job_ids]

        for jid, job in jobs:
            if job.future is not None:
                try:
                    job.future.result(timeout=timeout)
                except Exception as exc:
                    logger.error("Batch job %s failed: %s", jid, exc)
            if job.result is not None:
                results_map[jid] = job.result

        # Return in order
        ordered = []
        for jid in job_ids:
            result = results_map.get(jid, {"error": "evaluation failed"})
            result = dict(result)
            result["_job_id"] = jid
            ordered.append(result)

        return ordered

    # ── Lifecycle ─────────────────────────────────────────────────────

    def shutdown(self, wait: bool = True) -> None:
        """Shut down the background executor.

        Args:
            wait: If True, wait for pending evaluations to finish.
        """
        if not self._closed:
            self._closed = True
            self._executor.shutdown(wait=wait)
            logger.info(
                "RagEvaluator shut down (completed=%d)", self.completed_count
            )

    def clear(self) -> None:
        """Clear all stored results."""
        with self._lock:
            done_ids = [
                jid for jid, job in self._jobs.items() if job.result is not None
            ]
            for jid in done_ids:
                del self._jobs[jid]

    def __enter__(self) -> RagEvaluator:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.shutdown(wait=True)

    def __del__(self) -> None:
        try:
            self.shutdown(wait=False)
        except Exception:
            pass

    # ── Internal ──────────────────────────────────────────────────────

    def _run_eval(self, job: EvalJob) -> None:
        """Run a single evaluation in a background thread."""
        try:
            result = asyncio.run(
                evaluate_trace(
                    question=job.question,
                    answer=job.answer,
                    contexts=job.contexts,
                    ground_truth=job.ground_truth,
                    config=self._config,
                )
            )
            with self._lock:
                job.result = result
            logger.info(
                "Job %s completed (score=%.2f)",
                job.id,
                result.get("overall_score") or 0,
            )
        except Exception as exc:
            logger.exception("Job %s failed", job.id)
            with self._lock:
                job.error = str(exc)
                job.result = {
                    "error": str(exc),
                    "overall_score": None,
                    "reasoning_summary": f"Evaluation failed: {exc}",
                }
