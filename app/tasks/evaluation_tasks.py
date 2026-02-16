from app.services.evaluation_service import evaluate_trace_and_persist
from app.tasks.celery_app import celery_app


@celery_app.task(
    bind=True,
    name="app.tasks.evaluation_tasks.evaluate_trace_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def evaluate_trace_task(self, trace_id: str) -> None:
    evaluate_trace_and_persist(trace_id)
