from fastapi import APIRouter

from app.metrics.definitions import METRIC_DEFINITIONS

router = APIRouter()


@router.get(
    "/definitions",
    summary="Metrik tanımları ve açıklamaları",
    description=(
        "Tüm metriklerin adı, açıklaması, aralığı ve threshold bazlı "
        "dinamik açıklamalarını döner. UI/client bir kez çekip cache'leyebilir."
    ),
    responses={
        200: {"description": "Metrik tanımları başarıyla döndü"},
    },
)
def get_metric_definitions() -> list[dict]:
    """Return the full metric catalog with thresholds and explanations."""
    return METRIC_DEFINITIONS
