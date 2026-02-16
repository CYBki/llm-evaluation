import asyncio
from uuid import UUID

from app.config import settings
from app.database import SessionLocal
from app.evaluation import evaluate_trace
from app.models.evaluation import EvaluationResult
from app.models.trace import Trace


def enqueue_trace_evaluation(trace_id: UUID | str) -> None:
    trace_id_str = str(trace_id)

    if settings.evaluation_mode.lower() == "async":
        from app.tasks.evaluation_tasks import evaluate_trace_task

        evaluate_trace_task.delay(trace_id_str)
        return

    evaluate_trace_and_persist(trace_id_str)


def evaluate_trace_and_persist(trace_id: str) -> None:
    db = SessionLocal()
    try:
        trace = db.query(Trace).filter(Trace.id == trace_id).first()
        if not trace:
            return

        try:
            result = asyncio.run(evaluate_trace(trace.question, trace.answer, trace.contexts))
        except Exception:
            trace.status = "failed"
            db.add(trace)
            db.commit()
            return

        evaluation = db.query(EvaluationResult).filter(EvaluationResult.trace_id == trace.id).first()
        if not evaluation:
            evaluation = EvaluationResult(trace_id=trace.id)

        evaluation.clarity = result.get("clarity")
        evaluation.specificity = result.get("specificity")
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

        trace.status = "completed" if _is_successful_result(result) else "failed"

        db.add(evaluation)
        db.add(trace)
        db.commit()
    finally:
        db.close()


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
