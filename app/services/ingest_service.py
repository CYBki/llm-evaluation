from sqlalchemy.orm import Session

from app.models.trace import Trace
from app.models.user import User
from app.schemas.ingest import TraceCreate


def create_trace(db: Session, user: User, payload: TraceCreate) -> Trace:
    trace = Trace(
        user_id=user.id,
        question=payload.question,
        answer=payload.answer,
        contexts=payload.contexts,
        meta=payload.metadata,
        status="pending",
    )
    db.add(trace)
    db.commit()
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
            meta=payload.metadata,
            status="pending",
        )
        db.add(trace)
        traces.append(trace)

    db.commit()

    for trace in traces:
        db.refresh(trace)

    return traces


def list_traces(db: Session, user: User, page: int, per_page: int) -> tuple[list[Trace], int]:
    query = db.query(Trace).filter(Trace.user_id == user.id).order_by(Trace.created_at.desc())
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return items, total


def get_trace_by_id(db: Session, user: User, trace_id: str) -> Trace | None:
    return db.query(Trace).filter(Trace.id == trace_id, Trace.user_id == user.id).first()
