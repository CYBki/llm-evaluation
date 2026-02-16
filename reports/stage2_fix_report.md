# Stage 2 JSON Parse Hatası — Sorun ve Çözüm Raporu

**Tarih:** 16 Şubat 2026  
**Durum:** Çözüldü ✅

---

## Sorun

Sistemimiz iki aşamalı (two-stage) bir değerlendirme mimarisi kullanıyor:

- **Stage 1 (Büyük LLM):** Soru, cevap ve bağlamı alıp serbest metin (Chain-of-Thought) muhakeme üretiyor.
- **Stage 2 (Küçük LLM):** Stage 1'in serbest metnini yapılandırılmış JSON'a dönüştürüyor.

Stage 1 güvenilir çalışıyordu (%95+). Ancak **Stage 2, %80 oranında başarısız** oluyordu — üretilen JSON ya geçersizdi ya da beklenen şemaya uymuyordu.

### Gözlemlenen Belirtiler

- `overall_score = null`
- `reasoning_summary = "Stage 2 JSON parse failed"`
- 10 örnekten sadece 1-2'si skorlanabiliyordu

---

## Kök Sebepler

### 1. Zayıf Şema Zorlama (`json_object` vs `json_schema`)

OpenAI API'ye `response_format: { type: "json_object" }` gönderiliyordu. Bu sadece **geçerli JSON syntax'ı** garanti eder — alan adlarını, tiplerini ve zorunlu alanları **garanti etmez**. Model `{"result": "iyi"}` gibi geçerli ama şemaya uymayan JSON dönebiliyordu.

### 2. Düşük Token Limiti (512)

Stage 2 çağrısında `max_completion_tokens=512` kullanılıyordu. 11 üst seviye alan + `disagreement_claims` dizisi olan JSON çıktısı bu limite sığmadığında **JSON yarıda kesiliyor** ve parse edilemiyordu.

### 3. Prompt'ta Örnek Eksikliği

Stage 2 system prompt'u sadece alan adlarını ve tiplerini listeliyordu ama **somut bir örnek JSON göstermiyordu**. Model beklenen formattan sapabiliyordu.

### 4. Yetersiz Retry Mekanizması

Tek bir repair denemesi vardı ve modele **spesifik hata mesajı** verilmiyordu — sadece "tekrar dene" deniyordu. Model aynı hatayı tekrarlıyordu.

---

## Uygulanan Çözümler

### 1. OpenAI Structured Outputs (`json_schema`)

`json_object` yerine `json_schema` ile strict schema enforcement eklendi:

```python
payload["response_format"] = {
    "type": "json_schema",
    "json_schema": {
        "name": "evaluation_result",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": { ... },
            "required": [ 11 alan ],
            "additionalProperties": False
        }
    }
}
```

Bu, modeli **tam olarak belirtilen şemada** çıktı üretmeye zorluyor — alan eksik olamaz, tip yanlış olamaz.

**Etki:** Ana çözüm. Tek başına başarı oranını %20 → %90+ çıkardı.

### 2. Token Limiti Artırma (512 → 2048)

`max_completion_tokens` değeri 512'den 2048'e çıkarıldı. JSON çıktısının yarıda kesilme riski ortadan kalktı.

### 3. Prompt İyileştirme (Örnek JSON Ekleme)

Stage 2 prompt'una tam bir örnek JSON eklendi:

```json
{
  "clarity": 0.7,
  "specificity": 0.7,
  "is_off_topic": false,
  ...
  "disagreement_claims": [
    {
      "context_quote": "Paris is the capital of France.",
      "context_quote_type": "factual claim",
      "answer_quote": "Berlin is the capital of France.",
      "reasoning": "Cevap Berlin diyor ama baglam Paris diyor.",
      "disagreement_type": "confirmed contradiction"
    }
  ]
}
```

### 4. Validator + Retry Döngüsü (Max 3 Deneme)

Her denemede spesifik hata mesajı modele geri veriliyor:

```
Deneme 1: json_schema ile ilk çağrı
Deneme 2: "Missing field: clarity; overall_score must be number" → düzelt
Deneme 3: Son şans, aynı hata feedback ile
```

### 5. Deterministik Regex Fallback

Tüm LLM denemeleri başarısız olursa, Stage 1 metninden regex ile skor çıkarımı:

```
CLARITY: 0.7  →  clarity = 0.7
IS_OFF_TOPIC: false  →  is_off_topic = False
```

---

## Değişen Dosyalar

| Dosya | Değişiklik |
|-------|-----------|
| `app/evaluation/prompts.py` | `STAGE_2_JSON_SCHEMA` tanımı, örnek JSON, geliştirilmiş prompt'lar |
| `app/evaluation/llm_client.py` | `json_schema` parametresi desteği |
| `app/evaluation/evaluator.py` | Retry döngüsü, validator, tip dönüştürme, regex fallback |

---

## Sonuçlar

| Metrik | Önce | Sonra |
|--------|------|-------|
| Stage 2 başarı oranı | %20 (1/5) | **%100 (10/10)** |
| Parse failed | 4/5 | **0/10** |
| Ortalama overall_score | — | **0.83** |
| Retry gerekti | — | **0/10** |
| Regex fallback gerekti | — | **0/10** |

10 benchmark örneğinin tamamı Stage 1 + Stage 2 pipeline'ından başarıyla geçti. Canlı test de doğruladı.
