from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.trace import Trace
from app.models.user import User
from app.metrics.definitions import build_evaluation_commentary, get_verdict
from app.schemas.ingest import (
    DetailsResponse,
    EvaluationDetailResponse,
    EvaluationResponse,
    FlagsResponse,
    MultiAgentEvaluationDetailResponse,
    MultiAgentEvaluationResponse,
    ScoresResponse,
    StepEvaluationResponse,
    TraceDetailResponse,
    TraceListResponse,
    TraceResponse,
    VerdictsResponse,
)
from app.services.ingest_service import get_trace_by_id, list_traces

router = APIRouter()


def _build_scores(evaluation) -> ScoresResponse:
    return ScoresResponse(
        clarity=evaluation.clarity,
        coherence=evaluation.coherence,
        helpfulness=evaluation.helpfulness,
        completeness=evaluation.completeness,
        answer_relevancy=evaluation.answer_relevancy,
        context_precision=evaluation.context_precision,
        context_recall=evaluation.context_recall,
        faithfulness=evaluation.faithfulness,
        hallucination_score=evaluation.hallucination_score,
        citation_check=evaluation.citation_check,
    )


def _build_flags(evaluation) -> FlagsResponse:
    return FlagsResponse(
        is_off_topic=evaluation.is_off_topic,
        is_deflection=evaluation.is_deflection,
    )


def _build_details(evaluation) -> DetailsResponse:
    return DetailsResponse(
        hallucination_claims=evaluation.hallucination_claims or [],
        completeness_key_points=evaluation.completeness_key_points or [],
    )


def _build_verdicts(evaluation) -> VerdictsResponse:
    return VerdictsResponse(
        overall_score=get_verdict("overall_score", evaluation.overall_score),
        clarity=get_verdict("clarity", evaluation.clarity),
        coherence=get_verdict("coherence", evaluation.coherence),
        helpfulness=get_verdict("helpfulness", evaluation.helpfulness),
        completeness=get_verdict("completeness", evaluation.completeness),
        answer_relevancy=get_verdict("answer_relevancy", evaluation.answer_relevancy),
        context_precision=get_verdict(
            "context_precision", evaluation.context_precision
        ),
        context_recall=get_verdict("context_recall", evaluation.context_recall),
        faithfulness=get_verdict("faithfulness", evaluation.faithfulness),
        hallucination_score=get_verdict(
            "hallucination_score", evaluation.hallucination_score
        ),
        citation_check=get_verdict("citation_check", evaluation.citation_check),
    )


def _build_commentary(evaluation) -> str | None:
    """Build 1-2 sentence overall commentary from evaluation scores."""
    scores = {
        "clarity": evaluation.clarity,
        "coherence": evaluation.coherence,
        "helpfulness": evaluation.helpfulness,
        "completeness": evaluation.completeness,
        "answer_relevancy": evaluation.answer_relevancy,
        "context_precision": evaluation.context_precision,
        "context_recall": evaluation.context_recall,
        "faithfulness": evaluation.faithfulness,
        "hallucination_score": evaluation.hallucination_score,
        "citation_check": evaluation.citation_check,
    }
    return build_evaluation_commentary(evaluation.overall_score, scores)


def _build_step_evaluations(trace: Trace) -> list[StepEvaluationResponse]:
    """Build step-level evaluation responses from trace's step_evaluation_results."""
    step_evals = getattr(trace, "step_evaluation_results", None)
    if not step_evals:
        return []
    return [
        StepEvaluationResponse(
            step_index=se.step_index,
            agent_name=se.agent_name,
            overall_score=se.overall_score,
            confidence=se.evaluation_confidence,
            scores=_build_scores(se),
            verdicts=_build_verdicts(se),
            flags=_build_flags(se),
            reasoning_summary=se.reasoning_summary,
            details=_build_details(se),
        )
        for se in step_evals
    ]


def _is_multi_agent(trace: Trace) -> bool:
    """Check if trace has step evaluation results."""
    step_evals = getattr(trace, "step_evaluation_results", None)
    return bool(step_evals)


def _to_trace_response(trace: Trace) -> TraceResponse:
    evaluation = trace.evaluation_result
    is_multi = _is_multi_agent(trace)

    if evaluation and is_multi:
        eval_response = MultiAgentEvaluationResponse(
            overall_score=evaluation.overall_score,
            confidence=evaluation.evaluation_confidence,
            scores=_build_scores(evaluation),
            verdicts=_build_verdicts(evaluation),
            flags=_build_flags(evaluation),
            reasoning_summary=evaluation.reasoning_summary,
            details=_build_details(evaluation),
            evaluation_commentary=_build_commentary(evaluation),
            evaluation_duration_ms=evaluation.evaluation_duration_ms,
            pipeline_score=evaluation.pipeline_score,
            pipeline_verdict=get_verdict("overall_score", evaluation.pipeline_score),
            step_evaluations=_build_step_evaluations(trace),
        )
    elif evaluation:
        eval_response = EvaluationResponse(
            overall_score=evaluation.overall_score,
            confidence=evaluation.evaluation_confidence,
            scores=_build_scores(evaluation),
            verdicts=_build_verdicts(evaluation),
            flags=_build_flags(evaluation),
            reasoning_summary=evaluation.reasoning_summary,
            details=_build_details(evaluation),
            evaluation_commentary=_build_commentary(evaluation),
            evaluation_duration_ms=evaluation.evaluation_duration_ms,
        )
    else:
        eval_response = None

    return TraceResponse(
        id=str(trace.id),
        question=trace.question,
        answer=trace.answer,
        contexts=trace.contexts,
        metadata=trace.meta,
        status=trace.status,
        created_at=trace.created_at,
        evaluation=eval_response,
    )


def _to_trace_detail_response(trace: Trace) -> TraceDetailResponse:
    evaluation = trace.evaluation_result
    is_multi = _is_multi_agent(trace)

    if evaluation and is_multi:
        eval_response = MultiAgentEvaluationDetailResponse(
            overall_score=evaluation.overall_score,
            confidence=evaluation.evaluation_confidence,
            scores=_build_scores(evaluation),
            verdicts=_build_verdicts(evaluation),
            flags=_build_flags(evaluation),
            reasoning_summary=evaluation.reasoning_summary,
            details=_build_details(evaluation),
            evaluation_commentary=_build_commentary(evaluation),
            evaluation_duration_ms=evaluation.evaluation_duration_ms,
            stage_1_reasoning=evaluation.stage_1_reasoning,
            disagreement_claims=evaluation.disagreement_claims,
            model_used=evaluation.model_used,
            prompt_version=evaluation.prompt_version,
            rubric_version=evaluation.rubric_version,
            pipeline_score=evaluation.pipeline_score,
            pipeline_verdict=get_verdict("overall_score", evaluation.pipeline_score),
            step_evaluations=_build_step_evaluations(trace),
        )
    elif evaluation:
        eval_response = EvaluationDetailResponse(
            overall_score=evaluation.overall_score,
            confidence=evaluation.evaluation_confidence,
            scores=_build_scores(evaluation),
            verdicts=_build_verdicts(evaluation),
            flags=_build_flags(evaluation),
            reasoning_summary=evaluation.reasoning_summary,
            details=_build_details(evaluation),
            evaluation_commentary=_build_commentary(evaluation),
            evaluation_duration_ms=evaluation.evaluation_duration_ms,
            stage_1_reasoning=evaluation.stage_1_reasoning,
            disagreement_claims=evaluation.disagreement_claims,
            model_used=evaluation.model_used,
            prompt_version=evaluation.prompt_version,
            rubric_version=evaluation.rubric_version,
        )
    else:
        eval_response = None

    return TraceDetailResponse(
        id=str(trace.id),
        question=trace.question,
        answer=trace.answer,
        contexts=trace.contexts,
        metadata=trace.meta,
        status=trace.status,
        created_at=trace.created_at,
        evaluation=eval_response,
    )


@router.get(
    "",
    response_model=TraceListResponse,
    summary="Trace listesi",
    description="Kullanıcının trace'lerini sayfalanmış olarak listeler. Her trace'de evaluation sonuçları (skorlar, bayraklar, özet) yer alır.",
    responses={
        200: {"description": "Trace listesi başarıyla döndü"},
        401: {"description": "Geçersiz veya eksik API key"},
    },
)
def get_traces(
    page: int = Query(default=1, ge=1, description="Sayfa numarası (1'den başlar)"),
    per_page: int = Query(
        default=20, ge=1, le=100, description="Sayfa başına trace sayısı (max 100)"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TraceListResponse:
    """Kullanıcının tüm trace'lerini sayfalanmış şekilde döner."""
    traces, total = list_traces(db, current_user, page, per_page)
    items = [_to_trace_response(trace) for trace in traces]
    return TraceListResponse(items=items, page=page, per_page=per_page, total=total)


@router.get(
    "/{trace_id}",
    summary="Trace detayı",
    description="Tek bir trace'in detayını döner. `detail=summary` ile özet, `detail=full` ile stage_1_reasoning, disagreement_claims dahil tüm bilgiler gelir.",
    responses={
        200: {"description": "Trace detayı başarıyla döndü"},
        400: {"description": "Geçersiz trace ID formatı"},
        401: {"description": "Geçersiz veya eksik API key"},
        404: {"description": "Trace bulunamadı"},
    },
)
def get_trace(
    trace_id: str,
    detail: str = Query(
        default="summary",
        regex="^(summary|full)$",
        description="Detay seviyesi: 'summary' veya 'full'",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TraceResponse | TraceDetailResponse:
    try:
        UUID(trace_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid trace ID format"
        )
    trace = get_trace_by_id(db, current_user, trace_id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found"
        )

    if detail == "full":
        return _to_trace_detail_response(trace)
    return _to_trace_response(trace)
