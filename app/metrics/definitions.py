"""
Metric definitions with thresholds and dynamic explanations.
Used by:
  - GET /api/v1/metrics/definitions  → full catalog
  - Trace responses                  → verdict per score
"""

from __future__ import annotations

METRIC_DEFINITIONS: list[dict] = [
    {
        "key": "hallucination_score",
        "label": "Halüsinasyon Skoru",
        "description": "Cevabın kaynaklara sadakat (faithfulness) oranını ölçer. 1.0 = tamamen kaynaklara dayalı, 0.0 = tamamen uydurma.",
        "range": [0.0, 1.0],
        "good_direction": "high",
        "thresholds": [
            {"level": "good",     "min": 0.8, "max": 1.0,  "explanation": "Cevap tamamen kaynaklara dayalı, uydurma iddia yok."},
            {"level": "warning",  "min": 0.5, "max": 0.8,  "explanation": "Cevabın büyük kısmı doğru ama birkaç iddia kaynakla desteklenmiyor. Kontrol önerilir."},
            {"level": "bad",      "min": 0.2, "max": 0.5,  "explanation": "Ciddi miktarda desteksiz iddia var. Kullanıcıya sunulmadan düzeltilmeli."},
            {"level": "critical", "min": 0.0, "max": 0.2,  "explanation": "Cevabın çoğu uydurma. Kaynaklarla neredeyse hiç örtüşmüyor."},
        ],
    },
    {
        "key": "faithfulness",
        "label": "Sadakat (Faithfulness)",
        "description": "Cevaptaki iddiaların context'e sadık olma oranı. Her iddia ikili (faithful/unfaithful) olarak değerlendirilir. 1.0 = tüm iddialar context'te var, 0.0 = hiçbir iddia desteklenmiyor.",
        "range": [0.0, 1.0],
        "good_direction": "high",
        "thresholds": [
            {"level": "good",     "min": 0.8, "max": 1.0,  "explanation": "Cevaptaki iddiaların büyük çoğunluğu context'le destekleniyor."},
            {"level": "warning",  "min": 0.5, "max": 0.8,  "explanation": "Bazı iddialar context'te desteklenmiyor, kontrol edilmeli."},
            {"level": "bad",      "min": 0.2, "max": 0.5,  "explanation": "İddiaların yarısından fazlası desteksiz. Cevap güvenilir değil."},
            {"level": "critical", "min": 0.0, "max": 0.2,  "explanation": "Cevap neredeyse tamamen context dışı. Büyük sadakat sorunu."},
        ],
    },
    {
        "key": "answer_relevancy",
        "label": "Cevap İlgililiği",
        "description": "Cevabın soruyla ne kadar ilgili olduğunu ölçer.",
        "range": [0.0, 1.0],
        "good_direction": "high",
        "thresholds": [
            {"level": "good",     "min": 0.8, "max": 1.0,  "explanation": "Cevap soruyla doğrudan ilgili, tam karşılıyor."},
            {"level": "warning",  "min": 0.5, "max": 0.8,  "explanation": "Cevap kısmen ilgili ama sorunun bazı yönleri atlanmış veya konu dışına çıkılmış."},
            {"level": "bad",      "min": 0.0, "max": 0.5,  "explanation": "Cevap soruyla çok az ilgili veya tamamen farklı bir konuya kayıyor."},
        ],
    },
    {
        "key": "context_precision",
        "label": "Context Hassasiyeti",
        "description": "Getirilen context'lerin soruyla ilgili olma oranını ölçer.",
        "range": [0.0, 1.0],
        "good_direction": "high",
        "thresholds": [
            {"level": "good",     "min": 0.8, "max": 1.0,  "explanation": "Getirilen context'lerin tamamına yakını soruyla ilgili, gereksiz bilgi yok."},
            {"level": "warning",  "min": 0.5, "max": 0.8,  "explanation": "Context'lerin bir kısmı ilgisiz. Retriever ayarları gözden geçirilmeli."},
            {"level": "bad",      "min": 0.0, "max": 0.5,  "explanation": "Getirilen context'lerin çoğu soruyla alakasız. Retriever ciddi şekilde iyileştirilmeli."},
        ],
    },
    {
        "key": "context_recall",
        "label": "Context Kapsamı",
        "description": "Soruyu cevaplamak için gereken bilgilerin context'lerde bulunma oranını ölçer.",
        "range": [0.0, 1.0],
        "good_direction": "high",
        "thresholds": [
            {"level": "good",     "min": 0.8, "max": 1.0,  "explanation": "Soruyu cevaplamak için gereken bilgilerin tamamı context'lerde mevcut."},
            {"level": "warning",  "min": 0.5, "max": 0.8,  "explanation": "Bazı kritik bilgiler context'lerde eksik. Cevap eksik kalabilir."},
            {"level": "bad",      "min": 0.0, "max": 0.5,  "explanation": "Gereken bilgilerin büyük kısmı context'lerde yok. Knowledge base genişletilmeli."},
        ],
    },
    {
        "key": "completeness",
        "label": "Tamlık",
        "description": "Cevabın sorunun tüm yönlerini kapsama derecesini ölçer.",
        "range": [0.0, 1.0],
        "good_direction": "high",
        "thresholds": [
            {"level": "good",     "min": 0.8, "max": 1.0, "explanation": "Cevap sorunun tüm yönlerini kapsıyor, eksik nokta yok."},
            {"level": "warning",  "min": 0.5, "max": 0.8, "explanation": "Cevap ana noktayı karşılıyor ama bazı detaylar eksik."},
            {"level": "bad",      "min": 0.0, "max": 0.5, "explanation": "Cevap çok yüzeysel veya sorunun önemli kısımlarını atlıyor."},
        ],
    },
    {
        "key": "coherence",
        "label": "Tutarlılık",
        "description": "Cevabın iç tutarlılığını ve mantıksal akışını ölçer.",
        "range": [0.0, 1.0],
        "good_direction": "high",
        "thresholds": [
            {"level": "good",     "min": 0.8, "max": 1.0, "explanation": "Cevap tutarlı, mantıksal akış sorunsuz."},
            {"level": "warning",  "min": 0.5, "max": 0.8, "explanation": "Cevapta küçük tutarsızlıklar veya kopuk geçişler var."},
            {"level": "bad",      "min": 0.0, "max": 0.5, "explanation": "Cevap çelişkili veya mantıksal olarak dağınık."},
        ],
    },
    {
        "key": "clarity",
        "label": "Açıklık",
        "description": "Cevabın ne kadar açık ve anlaşılır olduğunu ölçer.",
        "range": [0.0, 1.0],
        "good_direction": "high",
        "thresholds": [
            {"level": "good",     "min": 0.8, "max": 1.0, "explanation": "Cevap açık, anlaşılır ve iyi yapılandırılmış."},
            {"level": "warning",  "min": 0.5, "max": 0.8, "explanation": "Cevap anlaşılıyor ama bazı ifadeler belirsiz veya gereksiz karmaşık."},
            {"level": "bad",      "min": 0.0, "max": 0.5, "explanation": "Cevap belirsiz, karışık veya anlaşılması güç."},
        ],
    },
    {
        "key": "helpfulness",
        "label": "Faydalılık",
        "description": "Cevabın kullanıcıya pratik fayda sağlama derecesini ölçer.",
        "range": [0.0, 1.0],
        "good_direction": "high",
        "thresholds": [
            {"level": "good",     "min": 0.8, "max": 1.0, "explanation": "Cevap kullanıcının ihtiyacını tam karşılıyor, pratik ve faydalı."},
            {"level": "warning",  "min": 0.5, "max": 0.8, "explanation": "Cevap kısmen faydalı ama daha pratik veya spesifik olabilirdi."},
            {"level": "bad",      "min": 0.0, "max": 0.5, "explanation": "Cevap kullanıcıya fayda sağlamıyor, genel veya işe yaramaz."},
        ],
    },
    {
        "key": "citation_check",
        "label": "Kaynak Doğruluğu",
        "description": "Cevaptaki iddiaların doğru kaynaklara referans verip vermediğini ölçer.",
        "range": [0.0, 1.0],
        "good_direction": "high",
        "thresholds": [
            {"level": "good",     "min": 0.8, "max": 1.0, "explanation": "İddialar doğru kaynaklara referans veriyor."},
            {"level": "warning",  "min": 0.5, "max": 0.8, "explanation": "Bazı referanslar eksik veya yanlış kaynağa işaret ediyor."},
            {"level": "bad",      "min": 0.0, "max": 0.5, "explanation": "Referansların çoğu eksik veya hatalı. Kaynak eşleştirmesi gözden geçirilmeli."},
        ],
    },
    {
        "key": "overall_score",
        "label": "Genel Skor",
        "description": "Tüm metriklerin ağırlıklı birleşiminden oluşan genel kalite skoru.",
        "range": [0.0, 1.0],
        "good_direction": "high",
        "thresholds": [
            {"level": "good",     "min": 0.8, "max": 1.0, "explanation": "Cevap genel olarak yüksek kaliteli. Tüm metrikler iyi seviyede."},
            {"level": "warning",  "min": 0.5, "max": 0.8, "explanation": "Cevap kabul edilebilir ama iyileştirme alanları var. Detaylı metrikleri inceleyin."},
            {"level": "bad",      "min": 0.0, "max": 0.5, "explanation": "Cevap kalitesi düşük. Birden fazla metrikte ciddi sorunlar mevcut."},
        ],
    },
]

# ── Index for fast lookup ───────────────────────────────────────────────

_METRIC_MAP: dict[str, dict] = {m["key"]: m for m in METRIC_DEFINITIONS}


def get_verdict(metric_key: str, value: float | None) -> str | None:
    """Return verdict label (good / warning / bad / critical) for a score."""
    if value is None:
        return None
    metric = _METRIC_MAP.get(metric_key)
    if not metric:
        return None
    for t in metric["thresholds"]:
        if t["min"] <= value <= t["max"]:
            return t["level"]
    return None


def get_verdict_with_explanation(metric_key: str, value: float | None) -> dict | None:
    """Return verdict + context-aware explanation for a score."""
    if value is None:
        return None
    metric = _METRIC_MAP.get(metric_key)
    if not metric:
        return None
    for t in metric["thresholds"]:
        if t["min"] <= value <= t["max"]:
            return {"verdict": t["level"], "explanation": t["explanation"]}
    return None


def compute_all_verdicts(scores: dict[str, float | None]) -> dict[str, str | None]:
    """Given a dict of metric_key→value, return metric_key→verdict."""
    return {key: get_verdict(key, val) for key, val in scores.items()}
