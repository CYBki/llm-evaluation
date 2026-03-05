from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.trace import Trace
from app.models.user import User
from app.schemas.ingest import TraceCreate
from app.services.evaluation_service import enqueue_batch_evaluation, enqueue_trace_evaluation


def create_trace(db: Session, user: User, payload: TraceCreate) -> Trace:
    trace = Trace(
        user_id=user.id,
        question=payload.question,
        answer=payload.answer,
        contexts=payload.contexts,
        ground_truth=payload.ground_truth,
        meta=payload.metadata,
        webhook_url=payload.webhook_url,
        status="pending",
    )
    db.add(trace)
    db.commit()
    db.refresh(trace)

    enqueue_trace_evaluation(trace.id)
    db.refresh(trace)

    return trace


def create_traces_batch(db: Session, user: User, payloads: list[TraceCreate]) -> list[Trace]:
    traces: list[Trace] = []
    for payload in payloads:
        trace = Trace(
            user_id=user.id,
            question=payload.question,
            answer=payload.answer,
            contexts=payload.contexts,
            ground_truth=payload.ground_truth,
            meta=payload.metadata,
            webhook_url=payload.webhook_url,
            status="pending",
        )
        db.add(trace)
        traces.append(trace)

    db.commit()

    for trace in traces:
        db.refresh(trace)

    # Enqueue all evaluations at once (parallel in async mode,
    # background thread in sync mode)
    enqueue_batch_evaluation([str(t.id) for t in traces])

    return traces


def list_traces(db: Session, user: User, page: int, per_page: int) -> tuple[list[Trace], int]:
    base = db.query(Trace).filter(Trace.user_id == user.id)
    # Fetch per_page+1 items to detect has_next without a separate COUNT query
    # We still compute total for backward compat, but only on first page
    items = (
        base
        .options(
            joinedload(Trace.evaluation_result),
            selectinload(Trace.step_evaluation_results),
        )
        .order_by(Trace.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    # Only run COUNT on first page or when explicitly needed
    total = base.count() if page == 1 or items else 0
    return items, total


def get_trace_by_id(db: Session, user: User, trace_id: str) -> Trace | None:
    return (
        db.query(Trace)
        .options(
            joinedload(Trace.evaluation_result),
            selectinload(Trace.step_evaluation_results),
        )
        .filter(Trace.id == trace_id, Trace.user_id == user.id)
        .first()
    )
