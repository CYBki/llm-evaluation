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
            {
                "level": "good",
                "verdict_label": "Kaynaklara Sadık",
                "min": 0.8,
                "max": 1.0,
                "explanation": "Cevap tamamen kaynaklara dayalı, uydurma iddia yok.",
            },
            {
                "level": "warning",
                "verdict_label": "Kısmen Desteksiz",
                "min": 0.5,
                "max": 0.8,
                "explanation": "Cevabın büyük kısmı doğru ama birkaç iddia kaynakla desteklenmiyor. Kontrol önerilir.",
            },
            {
                "level": "bad",
                "verdict_label": "Ciddi Uydurma Riski",
                "min": 0.2,
                "max": 0.5,
                "explanation": "Ciddi miktarda desteksiz iddia var. Kullanıcıya sunulmadan düzeltilmeli.",
            },
            {
                "level": "critical",
                "verdict_label": "Tamamen Uydurma",
                "min": 0.0,
                "max": 0.2,
                "explanation": "Cevabın çoğu uydurma. Kaynaklarla neredeyse hiç örtüşmüyor.",
            },
        ],
    },
    {
        "key": "faithfulness",
        "label": "Sadakat (Faithfulness)",
        "description": "Cevaptaki iddiaların context'e sadık olma oranı. Her iddia ikili (faithful/unfaithful) olarak değerlendirilir. 1.0 = tüm iddialar context'te var, 0.0 = hiçbir iddia desteklenmiyor.",
        "range": [0.0, 1.0],
        "good_direction": "high",
        "thresholds": [
            {
                "level": "good",
                "verdict_label": "Yüksek Sadakat",
                "min": 0.8,
                "max": 1.0,
                "explanation": "Cevaptaki iddiaların büyük çoğunluğu context'le destekleniyor.",
            },
            {
                "level": "warning",
                "verdict_label": "Kısmi Sapma Var",
                "min": 0.5,
                "max": 0.8,
                "explanation": "Bazı iddialar context'te desteklenmiyor, kontrol edilmeli.",
            },
            {
                "level": "bad",
                "verdict_label": "Düşük Sadakat",
                "min": 0.2,
                "max": 0.5,
                "explanation": "İddiaların yarısından fazlası desteksiz. Cevap güvenilir değil.",
            },
            {
                "level": "critical",
                "verdict_label": "Sadakat Yok",
                "min": 0.0,
                "max": 0.2,
                "explanation": "Cevap neredeyse tamamen context dışı. Büyük sadakat sorunu.",
            },
        ],
    },
    {
        "key": "answer_relevancy",
        "label": "Cevap İlgililiği",
        "description": "Cevabın soruyla ne kadar ilgili olduğunu ölçer.",
        "range": [0.0, 1.0],
        "good_direction": "high",
        "thresholds": [
            {
                "level": "good",
                "verdict_label": "Soruya Tam Uygun",
                "min": 0.8,
                "max": 1.0,
                "explanation": "Cevap soruyla doğrudan ilgili, tam karşılıyor.",
            },
            {
                "level": "warning",
                "verdict_label": "Kısmen İlgili",
                "min": 0.5,
                "max": 0.8,
                "explanation": "Cevap kısmen ilgili ama sorunun bazı yönleri atlanmış veya konu dışına çıkılmış.",
            },
            {
                "level": "bad",
                "verdict_label": "Sorudan Kopuk",
                "min": 0.0,
                "max": 0.5,
                "explanation": "Cevap soruyla çok az ilgili veya tamamen farklı bir konuya kayıyor.",
            },
        ],
    },
    {
        "key": "context_precision",
        "label": "Context Hassasiyeti",
        "description": "Getirilen context'lerin soruyla ilgili olma oranını ölçer.",
        "range": [0.0, 1.0],
        "good_direction": "high",
        "thresholds": [
            {
                "level": "good",
                "verdict_label": "Hassas Bağlam Seçimi",
                "min": 0.8,
                "max": 1.0,
                "explanation": "Getirilen context'lerin tamamına yakını soruyla ilgili, gereksiz bilgi yok.",
            },
            {
                "level": "warning",
                "verdict_label": "Kısmen İlgisiz Bağlam",
                "min": 0.5,
                "max": 0.8,
                "explanation": "Context'lerin bir kısmı ilgisiz. Retriever ayarları gözden geçirilmeli.",
            },
            {
                "level": "bad",
                "verdict_label": "Zayıf Bağlam Seçimi",
                "min": 0.0,
                "max": 0.5,
                "explanation": "Getirilen context'lerin çoğu soruyla alakasız. Retriever ciddi şekilde iyileştirilmeli.",
            },
        ],
    },
    {
        "key": "context_recall",
        "label": "Context Kapsamı",
        "description": "Soruyu cevaplamak için gereken bilgilerin context'lerde bulunma oranını ölçer.",
        "range": [0.0, 1.0],
        "good_direction": "high",
        "thresholds": [
            {
                "level": "good",
                "verdict_label": "Kapsamlı Bilgi Erişimi",
                "min": 0.8,
                "max": 1.0,
                "explanation": "Soruyu cevaplamak için gereken bilgilerin tamamı context'lerde mevcut.",
            },
            {
                "level": "warning",
                "verdict_label": "Eksik Bilgi Mevcut",
                "min": 0.5,
                "max": 0.8,
                "explanation": "Bazı kritik bilgiler context'lerde eksik. Cevap eksik kalabilir.",
            },
            {
                "level": "bad",
                "verdict_label": "Yetersiz Bilgi Kapsamı",
                "min": 0.0,
                "max": 0.5,
                "explanation": "Gereken bilgilerin büyük kısmı context'lerde yok. Knowledge base genişletilmeli.",
            },
        ],
    },
    {
        "key": "completeness",
        "label": "Tamlık",
        "description": "Cevabın sorunun tüm yönlerini kapsama derecesini ölçer.",
        "range": [0.0, 1.0],
        "good_direction": "high",
        "thresholds": [
            {
                "level": "good",
                "verdict_label": "Eksiksiz Cevap",
                "min": 0.8,
                "max": 1.0,
                "explanation": "Cevap sorunun tüm yönlerini kapsıyor, eksik nokta yok.",
            },
            {
                "level": "warning",
                "verdict_label": "Kısmen Eksik",
                "min": 0.5,
                "max": 0.8,
                "explanation": "Cevap ana noktayı karşılıyor ama bazı detaylar eksik.",
            },
            {
                "level": "bad",
                "verdict_label": "Çok Yetersiz Kapsam",
                "min": 0.0,
                "max": 0.5,
                "explanation": "Cevap çok yüzeysel veya sorunun önemli kısımlarını atlıyor.",
            },
        ],
    },
    {
        "key": "coherence",
        "label": "Tutarlılık",
        "description": "Cevabın iç tutarlılığını ve mantıksal akışını ölçer.",
        "range": [0.0, 1.0],
        "good_direction": "high",
        "thresholds": [
            {
                "level": "good",
                "verdict_label": "Mantıksal Tutarlı",
                "min": 0.8,
                "max": 1.0,
                "explanation": "Cevap tutarlı, mantıksal akış sorunsuz.",
            },
            {
                "level": "warning",
                "verdict_label": "Küçük Tutarsızlıklar",
                "min": 0.5,
                "max": 0.8,
                "explanation": "Cevapta küçük tutarsızlıklar veya kopuk geçişler var.",
            },
            {
                "level": "bad",
                "verdict_label": "Dağınık ve Çelişkili",
                "min": 0.0,
                "max": 0.5,
                "explanation": "Cevap çelişkili veya mantıksal olarak dağınık.",
            },
        ],
    },
    {
        "key": "clarity",
        "label": "Açıklık",
        "description": "Cevabın ne kadar açık ve anlaşılır olduğunu ölçer.",
        "range": [0.0, 1.0],
        "good_direction": "high",
        "thresholds": [
            {
                "level": "good",
                "verdict_label": "Açık ve Anlaşılır",
                "min": 0.8,
                "max": 1.0,
                "explanation": "Cevap açık, anlaşılır ve iyi yapılandırılmış.",
            },
            {
                "level": "warning",
                "verdict_label": "Belirsiz İfadeler Var",
                "min": 0.5,
                "max": 0.8,
                "explanation": "Cevap anlaşılıyor ama bazı ifadeler belirsiz veya gereksiz karmaşık.",
            },
            {
                "level": "bad",
                "verdict_label": "Anlaşılması Güç",
                "min": 0.0,
                "max": 0.5,
                "explanation": "Cevap belirsiz, karışık veya anlaşılması güç.",
            },
        ],
    },
    {
        "key": "helpfulness",
        "label": "Faydalılık",
        "description": "Cevabın kullanıcıya pratik fayda sağlama derecesini ölçer.",
        "range": [0.0, 1.0],
        "good_direction": "high",
        "thresholds": [
            {
                "level": "good",
                "verdict_label": "Oldukça Faydalı",
                "min": 0.8,
                "max": 1.0,
                "explanation": "Cevap kullanıcının ihtiyacını tam karşılıyor, pratik ve faydalı.",
            },
            {
                "level": "warning",
                "verdict_label": "Kısmen Faydalı",
                "min": 0.5,
                "max": 0.8,
                "explanation": "Cevap kısmen faydalı ama daha pratik veya spesifik olabilirdi.",
            },
            {
                "level": "bad",
                "verdict_label": "Fayda Sağlamıyor",
                "min": 0.0,
                "max": 0.5,
                "explanation": "Cevap kullanıcıya fayda sağlamıyor, genel veya işe yaramaz.",
            },
        ],
    },
    {
        "key": "citation_check",
        "label": "Kaynak Doğruluğu",
        "description": "Cevaptaki iddiaların doğru kaynaklara referans verip vermediğini ölçer.",
        "range": [0.0, 1.0],
        "good_direction": "high",
        "thresholds": [
            {
                "level": "good",
                "verdict_label": "Doğru Kaynak Referansı",
                "min": 0.8,
                "max": 1.0,
                "explanation": "İddialar doğru kaynaklara referans veriyor.",
            },
            {
                "level": "warning",
                "verdict_label": "Eksik Referanslar Var",
                "min": 0.5,
                "max": 0.8,
                "explanation": "Bazı referanslar eksik veya yanlış kaynağa işaret ediyor.",
            },
            {
                "level": "bad",
                "verdict_label": "Hatalı Kaynak Eşleme",
                "min": 0.0,
                "max": 0.5,
                "explanation": "Referansların çoğu eksik veya hatalı. Kaynak eşleştirmesi gözden geçirilmeli.",
            },
        ],
    },
    {
        "key": "overall_score",
        "label": "Genel Skor",
        "description": "Tüm metriklerin ağırlıklı birleşiminden oluşan genel kalite skoru.",
        "range": [0.0, 1.0],
        "good_direction": "high",
        "thresholds": [
            {
                "level": "good",
                "verdict_label": "Yüksek Kaliteli Cevap",
                "min": 0.8,
                "max": 1.0,
                "explanation": "Cevap genel olarak yüksek kaliteli. Tüm metrikler iyi seviyede.",
            },
            {
                "level": "warning",
                "verdict_label": "İyileştirme Gerekli",
                "min": 0.5,
                "max": 0.8,
                "explanation": "Cevap kabul edilebilir ama iyileştirme alanları var. Detaylı metrikleri inceleyin.",
            },
            {
                "level": "bad",
                "verdict_label": "Düşük Kaliteli Cevap",
                "min": 0.0,
                "max": 0.5,
                "explanation": "Cevap kalitesi düşük. Birden fazla metrikte ciddi sorunlar mevcut.",
            },
        ],
    },
]

# ── Index for fast lookup ───────────────────────────────────────────────

_METRIC_MAP: dict[str, dict] = {m["key"]: m for m in METRIC_DEFINITIONS}


def get_verdict(metric_key: str, value: float | None) -> str | None:
    """Return descriptive verdict label (2-3 words) for a score."""
    if value is None:
        return None
    metric = _METRIC_MAP.get(metric_key)
    if not metric:
        return None
    for t in metric["thresholds"]:
        if t["min"] <= value <= t["max"]:
            return t["verdict_label"]
    return None


def get_verdict_level(metric_key: str, value: float | None) -> str | None:
    """Return raw verdict level (good / warning / bad / critical) for a score."""
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
    """Return verdict label + context-aware explanation for a score."""
    if value is None:
        return None
    metric = _METRIC_MAP.get(metric_key)
    if not metric:
        return None
    for t in metric["thresholds"]:
        if t["min"] <= value <= t["max"]:
            return {"verdict": t["verdict_label"], "explanation": t["explanation"]}
    return None


def compute_all_verdicts(scores: dict[str, float | None]) -> dict[str, str | None]:
    """Given a dict of metric_key→value, return metric_key→verdict_label."""
    return {key: get_verdict(key, val) for key, val in scores.items()}


# ── Evaluation Commentary ──────────────────────────────────────────────

_METRIC_LABELS: dict[str, str] = {m["key"]: m["label"] for m in METRIC_DEFINITIONS}

# Human-readable aspect descriptions for building natural commentary
_METRIC_ASPECT: dict[str, str] = {
    "hallucination_score": "kaynaklara sadakat",
    "faithfulness": "context'e bağlılık",
    "answer_relevancy": "soruyla ilgililik",
    "context_precision": "bağlam seçimi hassasiyeti",
    "context_recall": "bilgi kapsamı",
    "completeness": "cevap tamlığı",
    "coherence": "mantıksal tutarlılık",
    "clarity": "açıklık ve anlaşılırlık",
    "helpfulness": "pratik fayda",
    "citation_check": "kaynak referans doğruluğu",
}

# Reason templates for weak metrics — explains WHY the score dropped
_WEAKNESS_REASONS: dict[str, dict[str, str]] = {
    "hallucination_score": {
        "bad": "cevap kaynaklarda bulunmayan iddialar içerdiği için",
        "critical": "cevabın büyük kısmı uydurma bilgilerden oluştuğu için",
        "warning": "bazı iddiaların kaynaklarla tam örtüşmemesi nedeniyle",
    },
    "faithfulness": {
        "bad": "iddiaların önemli kısmı context ile desteklenemediği için",
        "critical": "cevap neredeyse tamamen context dışı bilgiler barındırdığı için",
        "warning": "bazı iddiaların context'te karşılığının bulunamaması nedeniyle",
    },
    "answer_relevancy": {
        "bad": "cevap soruyla yeterince ilgili olmadığı için",
        "warning": "cevabın sorunun bazı yönlerini atlaması nedeniyle",
    },
    "context_precision": {
        "bad": "getirilen bağlam bilgilerinin çoğunun soruyla alakasız olması nedeniyle",
        "warning": "bağlam seçiminde ilgisiz bilgiler bulunması nedeniyle",
    },
    "context_recall": {
        "bad": "soruyu cevaplamak için gerekli bilgilerin context'lerde eksik olması nedeniyle",
        "warning": "bazı kritik bilgilerin context'lerde bulunamaması nedeniyle",
    },
    "completeness": {
        "bad": "cevabın sorunun önemli kısımlarını atlayarak yüzeysel kalması nedeniyle",
        "warning": "eksik detaylar bulunması nedeniyle",
    },
    "coherence": {
        "bad": "cevapta çelişkili veya mantıksal olarak dağınık ifadeler olması nedeniyle",
        "warning": "küçük tutarsızlıklar ve kopuk geçişler bulunması nedeniyle",
    },
    "clarity": {
        "bad": "cevabın belirsiz, karışık ve anlaşılması güç olması nedeniyle",
        "warning": "bazı ifadelerin gereksiz karmaşık veya belirsiz olması nedeniyle",
    },
    "helpfulness": {
        "bad": "cevabın kullanıcıya pratik fayda sağlamaması nedeniyle",
        "warning": "cevabın yeterince spesifik ve pratik olmaması nedeniyle",
    },
    "citation_check": {
        "bad": "kaynak referanslarının büyük kısmının hatalı veya eksik olması nedeniyle",
        "warning": "bazı referansların eksik veya yanlış kaynağa işaret etmesi nedeniyle",
    },
}

# Strength descriptions for high-scoring metrics
_STRENGTH_DESC: dict[str, str] = {
    "hallucination_score": "tüm iddialar kaynaklarla destekleniyor",
    "faithfulness": "cevap tamamen context'e sadık kalıyor",
    "answer_relevancy": "cevap soruyu doğrudan ve tam karşılıyor",
    "context_precision": "getirilen bağlam bilgileri son derece isabetli",
    "context_recall": "gerekli bilgilerin tamamı context'lerde mevcut",
    "completeness": "sorunun tüm yönleri eksiksiz yanıtlanmış",
    "coherence": "mantıksal akış sorunsuz ve tutarlı",
    "clarity": "ifadeler açık ve anlaşılır",
    "helpfulness": "cevap pratik ve faydalı bilgi sunuyor",
    "citation_check": "kaynak referansları doğru ve eksiksiz",
}


def build_evaluation_commentary(
    overall_score: float | None,
    scores: dict[str, float | None],
) -> str | None:
    """Build a detailed 1-3 sentence commentary explaining why the score is what it is."""
    if overall_score is None:
        return None

    # Categorize metrics by performance level
    critical_metrics: list[tuple[str, float]] = []
    bad_metrics: list[tuple[str, float]] = []
    warning_metrics: list[tuple[str, float]] = []
    good_metrics: list[tuple[str, float]] = []
    excellent_metrics: list[tuple[str, float]] = []

    for key, val in scores.items():
        if val is None or key == "overall_score":
            continue
        level = get_verdict_level(key, val)
        if level == "critical":
            critical_metrics.append((key, val))
        elif level == "bad":
            bad_metrics.append((key, val))
        elif level == "warning":
            warning_metrics.append((key, val))
        elif level == "good":
            if val >= 0.95:
                excellent_metrics.append((key, val))
            else:
                good_metrics.append((key, val))

    parts: list[str] = [f"Genel skor: {overall_score:.2f}."]

    # ── Case 1: Critical or bad metrics exist — explain the drop
    if critical_metrics or bad_metrics:
        worst = critical_metrics + bad_metrics
        # Sort by score ascending (worst first)
        worst.sort(key=lambda x: x[1])

        reason_parts: list[str] = []
        for key, val in worst[:3]:  # max 3 worst metrics to mention
            level = get_verdict_level(key, val)
            label = _METRIC_LABELS.get(key, key)
            reasons = _WEAKNESS_REASONS.get(key, {})
            reason = reasons.get(level or "bad", f"{label} düşük olduğu için")
            reason_parts.append(f"{label} ({val:.2f}) — {reason}")

        parts.append(f" Genel skoru düşüren temel nedenler: {'; '.join(reason_parts)}.")

        # If there are also good aspects, mention them briefly
        if excellent_metrics:
            strong_aspects = [
                _STRENGTH_DESC.get(k, _METRIC_LABELS.get(k, k))
                for k, _ in excellent_metrics[:3]
            ]
            parts.append(f" Olumlu yön olarak {', '.join(strong_aspects)}.")

    # ── Case 2: Only warnings — acknowledge but note areas to improve
    elif warning_metrics:
        parts.append(" Cevap genel olarak kabul edilebilir düzeyde.")

        warn_details: list[str] = []
        for key, val in warning_metrics[:3]:
            label = _METRIC_LABELS.get(key, key)
            reasons = _WEAKNESS_REASONS.get(key, {})
            reason = reasons.get("warning", f"{label} alanında iyileştirme gerekiyor")
            warn_details.append(f"{label} ({val:.2f}) — {reason}")

        parts.append(f" İyileştirme alanları: {'; '.join(warn_details)}.")

        if excellent_metrics:
            strong_aspects = [
                _STRENGTH_DESC.get(k, _METRIC_LABELS.get(k, k))
                for k, _ in excellent_metrics[:3]
            ]
            parts.append(f" Güçlü yönler: {', '.join(strong_aspects)}.")

    # ── Case 3: All good/excellent — celebrate and explain strengths
    else:
        all_strong = excellent_metrics + good_metrics
        if not all_strong:
            parts.append(" Tüm metrikler iyi seviyede.")
        elif len(excellent_metrics) >= 3:
            strong_aspects = [
                _STRENGTH_DESC.get(k, _METRIC_LABELS.get(k, k))
                for k, _ in excellent_metrics
            ]
            parts.append(f" Cevap yüksek kalitede: {', '.join(strong_aspects)}.")
            if good_metrics:
                good_labels = [
                    f"{_METRIC_LABELS.get(k, k)} ({v:.2f})" for k, v in good_metrics[:2]
                ]
                parts.append(f" {', '.join(good_labels)} de iyi seviyede.")
        else:
            all_labels = [
                f"{_METRIC_LABELS.get(k, k)} ({v:.2f})"
                for k, v in sorted(all_strong, key=lambda x: -x[1])[:4]
            ]
            parts.append(
                f" Tüm metrikler iyi düzeyde; öne çıkanlar: {', '.join(all_labels)}."
            )

    return "".join(parts)
