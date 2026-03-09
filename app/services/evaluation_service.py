import asyncio
import hashlib
import json
import logging
import threading
import time
from contextlib import contextmanager
from typing import Generator
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.evaluation import evaluate_trace
from app.models.evaluation import EvaluationResult, StepEvaluationResult
from app.models.trace import Trace
from app.services.webhook_service import deliver_webhook

logger = logging.getLogger(__name__)


@contextmanager
def _get_db() -> Generator[Session, None, None]:
    """Scoped session for background / non-request contexts."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def enqueue_trace_evaluation(trace_id: UUID | str) -> None:
    trace_id_str = str(trace_id)

    if settings.evaluation_mode.lower() == "async":
        from app.tasks.evaluation_tasks import evaluate_trace_task

        evaluate_trace_task.delay(trace_id_str)
        logger.info("Enqueued async evaluation for trace %s", trace_id_str)
        return

    evaluate_trace_and_persist(trace_id_str)


def enqueue_batch_evaluation(trace_ids: list[str]) -> None:
    """Enqueue multiple trace evaluations efficiently.

    - async mode: Celery group for true parallelism across workers
    - sync mode: background thread to avoid blocking the HTTP response
    """
    if not trace_ids:
        return

    if settings.evaluation_mode.lower() == "async":
        from celery import group

        from app.tasks.evaluation_tasks import evaluate_trace_task

        job = group(evaluate_trace_task.s(tid) for tid in trace_ids)
        job.apply_async()
        logger.info("Enqueued Celery group for %d traces", len(trace_ids))
        return

    # Sync mode: run evaluations in a background thread so the HTTP
    # response returns immediately instead of blocking for minutes.
    def _run_batch(ids: list[str]) -> None:
        for tid in ids:
            try:
                evaluate_trace_and_persist(tid)
            except Exception:
                logger.exception("Background batch eval failed for trace %s", tid)

    thread = threading.Thread(
        target=_run_batch,
        args=(list(trace_ids),),
        name="batch-eval",
        daemon=False,  # non-daemon: allow in-flight evaluations to finish on shutdown
    )
    thread.start()
    _active_batch_threads.append(thread)
    logger.info("Started background thread for %d trace evaluations", len(trace_ids))


# Track non-daemon batch threads for graceful shutdown
_active_batch_threads: list[threading.Thread] = []


def wait_for_batch_threads(timeout: float = 60.0) -> None:
    """Wait for all running batch evaluation threads to finish (call on shutdown)."""
    for t in _active_batch_threads:
        if t.is_alive():
            logger.info(
                "Waiting for batch thread '%s' to finish (timeout=%.0fs)",
                t.name,
                timeout,
            )
            t.join(timeout=timeout)
    _active_batch_threads.clear()


def _apply_result_to_evaluation(evaluation: EvaluationResult, result: dict) -> None:
    """Map eval result dict fields onto an EvaluationResult ORM object."""
    evaluation.clarity = result.get("clarity")
    evaluation.is_off_topic = result.get("is_off_topic")
    evaluation.completeness = result.get("completeness")
    evaluation.coherence = result.get("coherence")
    evaluation.helpfulness = result.get("helpfulness")
    evaluation.is_deflection = result.get("is_deflection")
    evaluation.overall_score = result.get("overall_score")
    evaluation.evaluation_confidence = result.get("evaluation_confidence")
    evaluation.reasoning_summary = result.get("reasoning_summary")
    evaluation.disagreement_claims = result.get("disagreement_claims")
    evaluation.stage_1_reasoning = result.get("stage_1_reasoning")
    evaluation.raw_response = result.get("raw_response")
    evaluation.model_used = result.get("model_used")
    evaluation.prompt_version = result.get("prompt_version")
    evaluation.rubric_version = result.get("rubric_version")
    # RAG-specific
    evaluation.answer_relevancy = result.get("answer_relevancy")
    evaluation.faithfulness = result.get("faithfulness")
    evaluation.hallucination_score = result.get("hallucination_score")
    evaluation.citation_check = result.get("citation_check")
    evaluation.faithfulness_claims = result.get(
        "hallucination_claims"
    )  # faithfulness derived from same claims
    evaluation.hallucination_claims = result.get("hallucination_claims")
    evaluation.completeness_key_points = result.get("completeness_key_points")
    evaluation.context_precision = result.get("context_precision")
    evaluation.context_recall = result.get("context_recall")
    # Token usage & cost
    evaluation.prompt_tokens = result.get("prompt_tokens")
    evaluation.completion_tokens = result.get("completion_tokens")
    evaluation.total_tokens = result.get("total_tokens")
    evaluation.cost_usd = result.get("cost_usd")


def _apply_result_to_step(step_eval: StepEvaluationResult, result: dict) -> None:
    """Map eval result dict fields onto a StepEvaluationResult ORM object."""
    step_eval.clarity = result.get("clarity")
    step_eval.is_off_topic = result.get("is_off_topic")
    step_eval.completeness = result.get("completeness")
    step_eval.coherence = result.get("coherence")
    step_eval.helpfulness = result.get("helpfulness")
    step_eval.is_deflection = result.get("is_deflection")
    step_eval.overall_score = result.get("overall_score")
    step_eval.evaluation_confidence = result.get("evaluation_confidence")
    step_eval.reasoning_summary = result.get("reasoning_summary")
    step_eval.answer_relevancy = result.get("answer_relevancy")
    step_eval.faithfulness = result.get("faithfulness")
    step_eval.hallucination_score = result.get("hallucination_score")
    step_eval.citation_check = result.get("citation_check")
    step_eval.faithfulness_claims = result.get("hallucination_claims")
    step_eval.hallucination_claims = result.get("hallucination_claims")
    step_eval.completeness_key_points = result.get("completeness_key_points")
    step_eval.context_precision = result.get("context_precision")
    step_eval.context_recall = result.get("context_recall")
    step_eval.model_used = result.get("model_used")


def _compute_content_hash(
    question: str,
    answer: str,
    contexts: list[str] | None,
    ground_truth: str | None,
) -> str:
    """SHA-256 hash of evaluation inputs for cache lookup."""
    payload = json.dumps(
        {"q": question, "a": answer, "c": contexts or [], "g": ground_truth or ""},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _copy_evaluation(source: EvaluationResult, target: EvaluationResult) -> None:
    """Copy all metric fields from a cached evaluation to a new one."""
    for col in (
        "clarity",
        "is_off_topic",
        "completeness",
        "coherence",
        "helpfulness",
        "is_deflection",
        "overall_score",
        "evaluation_confidence",
        "reasoning_summary",
        "disagreement_claims",
        "stage_1_reasoning",
        "raw_response",
        "model_used",
        "prompt_version",
        "rubric_version",
        "answer_relevancy",
        "faithfulness",
        "hallucination_score",
        "citation_check",
        "faithfulness_claims",
        "hallucination_claims",
        "completeness_key_points",
        "context_precision",
        "context_recall",
        "content_hash",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cost_usd",
        "evaluation_duration_ms",
    ):
        setattr(target, col, getattr(source, col))


def _extract_steps(trace: Trace) -> list[dict] | None:
    """Return steps list from trace metadata, or None."""
    meta = trace.meta
    if not meta:
        return None
    steps = meta.get("steps")
    if not steps or not isinstance(steps, list):
        return None
    return steps


def evaluate_trace_and_persist(trace_id: str) -> None:
    """Sync entry point — delegates to async implementation via asyncio.run()."""
    asyncio.run(_evaluate_trace_async(trace_id))


async def _evaluate_trace_async(trace_id: str) -> None:
    with _get_db() as db:
        trace = db.query(Trace).filter(Trace.id == trace_id).first()
        if not trace:
            logger.warning("Trace %s not found for evaluation", trace_id)
            return

        # ── 0. Content hash for cache lookup ──
        content_hash = _compute_content_hash(
            trace.question, trace.answer, trace.contexts, trace.ground_truth
        )

        evaluation = (
            db.query(EvaluationResult)
            .filter(EvaluationResult.trace_id == trace.id)
            .first()
        )
        if not evaluation:
            evaluation = EvaluationResult(trace_id=trace.id)

        # ── Cache hit? Copy results from a previous evaluation with same inputs ──
        cached = (
            db.query(EvaluationResult)
            .filter(
                EvaluationResult.content_hash == content_hash,
                EvaluationResult.overall_score.isnot(None),
                EvaluationResult.trace_id != trace.id,
            )
            .first()
        )
        if cached:
            logger.info(
                "Cache hit for trace %s (hash=%s) — copying from eval %s",
                trace_id,
                content_hash[:12],
                cached.trace_id,
            )
            _copy_evaluation(cached, evaluation)
            trace.status = "completed"
            db.add(evaluation)
            db.add(trace)
            db.commit()
            return

        # ── 1. Trace-level evaluation (final answer) — cache miss ──
        eval_start = time.perf_counter()
        try:
            result = await evaluate_trace(
                trace.question, trace.answer, trace.contexts, trace.ground_truth
            )
        except Exception:
            logger.exception("Evaluation failed for trace %s", trace_id)
            trace.status = "failed"
            db.add(trace)
            db.commit()
            return
        eval_duration_ms = round((time.perf_counter() - eval_start) * 1000)

        _apply_result_to_evaluation(evaluation, result)
        evaluation.evaluation_duration_ms = eval_duration_ms
        evaluation.content_hash = content_hash

        # ── 2. Step-level evaluation (if multi-agent) — PARALLEL ──
        steps = _extract_steps(trace)
        if steps:
            logger.info(
                "Multi-agent trace %s detected with %d steps — running parallel step-level eval",
                trace_id,
                len(steps),
            )

            # Clear previous step evaluations (re-evaluation case)
            db.query(StepEvaluationResult).filter(
                StepEvaluationResult.trace_id == trace.id
            ).delete()

            # Build coroutines for all steps and run them concurrently
            step_coros = [
                evaluate_trace(
                    question=step.get("input", ""),
                    answer=step.get("output", ""),
                    contexts=step.get("contexts"),
                    ground_truth=None,
                )
                for step in steps
            ]
            step_results = await asyncio.gather(*step_coros, return_exceptions=True)

            step_scores: list[float] = []

            for step, step_result in zip(steps, step_results):
                step_index = step.get("step_index", 0)
                agent_name = step.get("agent", f"step_{step_index}")

                if isinstance(step_result, Exception):
                    logger.exception(
                        "Step %d eval failed for trace %s: %s",
                        step_index,
                        trace_id,
                        step_result,
                    )
                    continue

                step_eval = StepEvaluationResult(
                    trace_id=trace.id,
                    step_index=step_index,
                    agent_name=agent_name,
                )
                _apply_result_to_step(step_eval, step_result)
                db.add(step_eval)

                if step_eval.overall_score is not None:
                    step_scores.append(step_eval.overall_score)

                logger.info(
                    "Step %d (%s) eval done for trace %s — score=%.2f",
                    step_index,
                    agent_name,
                    trace_id,
                    step_eval.overall_score or 0.0,
                )

            # ── 3. Pipeline score = 50% trace + 50% avg(step scores) ──
            if step_scores:
                avg_step = sum(step_scores) / len(step_scores)
                trace_score = evaluation.overall_score or 0.0
                evaluation.pipeline_score = round(0.5 * trace_score + 0.5 * avg_step, 4)
                logger.info(
                    "Pipeline score for trace %s: %.4f (trace=%.2f, avg_step=%.2f)",
                    trace_id,
                    evaluation.pipeline_score,
                    trace_score,
                    avg_step,
                )

        trace.status = "completed" if _is_successful_result(result) else "failed"

        db.add(evaluation)
        db.add(trace)
        db.commit()
        logger.info(
            "Evaluation persisted for trace %s — status=%s", trace_id, trace.status
        )

        # ── Webhook callback ──
        if trace.webhook_url:
            deliver_webhook(trace, evaluation)


def _is_successful_result(result: dict) -> bool:
    raw_response = result.get("raw_response")
    if isinstance(raw_response, list):
        if not raw_response:
            return False
        for item in raw_response:
            if isinstance(item, dict) and (item.get("failed") or item.get("skipped")):
                return False
        return True

    if isinstance(raw_response, dict):
        if raw_response.get("failed") or raw_response.get("skipped"):
            return False
        return True

    return False
