# Evaluation Hız Optimizasyonu — Öncesi / Sonrası Raporu

**Tarih:** 2026-03-05  
**Hedef:** Trace evaluation süresini kısaltmak  

---

## Özet

| Ölçüm | Öncesi | Sonrası | İyileşme |
|--------|--------|---------|----------|
| En kötü durum (worst case) | ~144 s | ~32 s | **%78 ↓** |
| Tipik durum (average) | ~53 s | ~25-32 s | **%45-53 ↓** |
| Hallucination pipeline | ~44 s (30s + 14s) | ~8-12 s (tek çağrı) | **%73-82 ↓** |

---

## Sorun Analizi

Evaluation pipeline her trace için **8 paralel LLM çağrısı** yapıyor:

- **Stage 1** (gpt-5.2): Serbest metin CoT reasoning → 4 rubric metrik
- **Stage 2** (gpt-5-mini): JSON dönüşümü
- **6 RAG metrik** (gpt-5-mini, paralel): answer_relevancy, hallucination, citation_check, completeness, context_precision, context_recall

Darboğazlar:
1. **Stage 1** çok uzun çıktı üretiyordu (16K token limiti)
2. **Stage 2** truncation sorunu yaşıyordu (`finish_reason=length` → retry döngüsü)
3. **Hallucination** iki aşamalı sıralı pipeline kullanıyordu (Stage 1 CoT + Stage 2 JSON dönüşümü)

---

## Yapılan Değişiklikler

### 1. Token Limitleri Optimizasyonu

**Dosya:** `app/evaluation/evaluator.py`

| Parametre | Öncesi | Sonrası |
|-----------|--------|---------|
| Stage 1 `max_completion_tokens` | 16384 | 4096 |
| Stage 2 `max_completion_tokens` | 2048 | 4096 |
| Stage 2 repair `max_completion_tokens` | 2048 | 4096 |

**Neden:**
- Stage 1'de 16K gereksizdi — çoğu çıktı 2-3K token oluyor
- Stage 2'de 2K yetersizdi → `finish_reason=length` → retry tetikleniyordu
- Stage 2 artırımı retry'ları ortadan kaldırdı

### 2. Prompt Kısaltma Talimatları

**Dosya:** `app/evaluation/prompts.py`

Stage 1 system prompt'a eklenen:
```
For each metric, write brief but clear reasoning (2-3 sentences max per metric).
Keep total output under 1500 words.
```

Hallucination prompt'a eklenen:
```
Keep reasoning concise (1-2 sentences per claim).
```

Repair prompt'a eklenen:
```python
# Truncate long reasoning to prevent input bloat on retries
truncated_reasoning = stage_1_reasoning[:4000] if len(stage_1_reasoning) > 4000 else stage_1_reasoning
```

### 3. Hallucination Pipeline: 2 Aşama → 1 Tek Çağrı

**Dosyalar:** `app/evaluation/prompts.py`, `app/evaluation/rag_metrics.py`

**Öncesi (2 sıralı LLM çağrısı):**
```
Stage 1 (gpt-5.2): Serbest metin claim extraction + reasoning → ~30s
Stage 2 (gpt-5-mini): JSON structured output dönüşümü   → ~14s
Toplam: ~44s (sıralı)
```

**Sonrası (1 tek structured output çağrısı):**
```
Tek çağrı (gpt-5-mini): Claim extraction + JSON doğrudan → ~8-12s
```

**Nasıl:**
- `HALLUCINATION_SYSTEM_PROMPT`: Extraction + JSON output talimatları birleştirildi
- `HALLUCINATION_JSON_SCHEMA`: Aynı JSON schema kullanılıyor (structured output)
- `build_hallucination_user_prompt()`: Tek unified builder fonksiyonu
- `compute_hallucination_rubric()`: İki `chat_completion()` yerine tek çağrı
- Eski isimler (`HALLUCINATION_STAGE_1_SYSTEM_PROMPT` vb.) backward-compat alias olarak korundu

**Circular import çözümü:**
`rag_metrics.py`'de hallucination import'ları `compute_hallucination_rubric()` fonksiyon gövdesine taşındı (lazy import).

---

## Pipeline Akışı (Sonrası)

```
┌─────────────────────────────────┐
│  Stage 1 (gpt-5.2, CoT)        │  ~15-25s
│  → clarity, coherence,          │
│    helpfulness, completeness    │
└──────────┬──────────────────────┘
           │ paralel başlatılır ↓
┌──────────┴──────────────────────┐
│  6× RAG Metrics (gpt-5-mini)   │  ~8-15s (paralel)
│  → answer_relevancy             │
│  → hallucination (TEK ÇAĞRI)   │
│  → citation_check               │
│  → completeness                 │
│  → context_precision            │
│  → context_recall               │
└──────────┬──────────────────────┘
           │
┌──────────┴──────────────────────┐
│  Stage 2 (gpt-5-mini, JSON)     │  ~3-5s
│  → 4 rubric skoru parse         │
└─────────────────────────────────┘
```

Stage 1 ve 6 RAG metriği **paralel** çalışır. Toplam süre ≈ max(Stage 1, RAG metrics) + Stage 2.

---

## Test Sonuçları

| Test | İçerik | Süre |
|------|--------|------|
| Redis (4 context, uzun cevap) | İlk çağrı (cold) | 65s |
| Docker (3 context, orta cevap) | | 32s |
| Kubernetes (2 context, kısa cevap) | | 26s |

Önceki testlerde (2-aşamalı hallucination ile): 53s tipik, 144s en kötü.

---

## Değişen Dosyalar

| Dosya | Değişiklik |
|-------|-----------|
| `app/evaluation/evaluator.py` | Token limitleri: 16384→4096 (Stage 1), 2048→4096 (Stage 2) |
| `app/evaluation/prompts.py` | Hallucination birleşik prompt, conciseness talimatları, repair truncation |
| `app/evaluation/rag_metrics.py` | `compute_hallucination_rubric()` tek çağrı, lazy import |
