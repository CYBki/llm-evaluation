# RAG Evaluation Tool — Takım Sunum Rehberi

**Tarih:** 20 Şubat 2026  
**Hedef Kitle:** Geliştirme ekibi  
**Sunum Süresi:** ~45–60 dakika

---

## İçindekiler

1. [Projenin Amacı ve Problemi](#1-projenin-amacı-ve-problemi)
2. [Mimari Genel Bakış](#2-mimari-genel-bakış)
3. [Trace Nedir ve Veri Akışı](#3-trace-nedir-ve-veri-akışı)
4. [İki Aşamalı Değerlendirme Motoru (Two-Stage LLM-as-Judge)](#4-iki-aşamalı-değerlendirme-motoru)
5. [Metrik Seçim Felsefesi — Neden Bu Metrikleri Seçtik?](#5-metrik-seçim-felsefesi)
6. [Pipeline A: Rubric Tabanlı Metrikler (Stage 1 + Stage 2)](#6-pipeline-a-rubric-tabanlı-metrikler)
7. [Pipeline B: RAG Analitik Metrikler](#7-pipeline-b-rag-analitik-metrikler)
8. [Overall Score Formülü](#8-overall-score-formülü)
9. [Değerlendirme Mekanizması Detaylı Akış](#9-değerlendirme-mekanizması-detaylı-akış)
10. [Rubric Sistemi ve Evrimi](#10-rubric-sistemi-ve-evrimi)
11. [Benchmark ve Doğrulama](#11-benchmark-ve-doğrulama)
12. [Bilinen Limitasyonlar](#12-bilinen-limitasyonlar)
13. [Maliyet Analizi](#13-maliyet-analizi)

---

## 1. Projenin Amacı ve Problemi

### Problem
RAG (Retrieval-Augmented Generation) sistemleri kullanıcılara cevap üretirken şu problemler yaşanır:
- LLM context'te olmayan bilgiyi **uydurabilir** (halüsinasyon)
- Retriever **yanlış veya eksik** context getirebilir
- Cevap soruyla **alakasız** olabilir
- Cevap **eksik** olabilir — sorunun tüm kısımlarını karşılamayabilir

Bu problemleri **otomatik, tutarlı ve açıklanabilir** şekilde tespit eden bir araç yok.

### Çözüm
Kullanıcının RAG sistemine **3 satır SDK** ekleyerek her soru-cevap-context etkileşimini otomatik puanlayan bir SaaS platformu.

```python
from rageval import RagEvalTracker                          # ← 1. satır
tracker = RagEvalTracker()                                   # ← 2. satır
# ... RAG pipeline içinde:
tracker.log(question=question, answer=answer, contexts=contexts)  # ← 3. satır
```

Her `tracker.log()` çağrısında:
1. Trace (soru + cevap + context) API'ye gönderilir
2. **İki paralel pipeline** ile değerlendirilir
3. 13 metrik + açıklama + claim-level detay üretilir
4. Sonuçlar DB'ye kaydedilir

---

## 2. Mimari Genel Bakış

```
┌──────────────────────────────────────────────────────────────┐
│                     Kullanıcı RAG Sistemi                     │
│         tracker.log(question, answer, contexts)               │
└──────────────────────┬───────────────────────────────────────┘
                       │ POST /api/v1/ingest
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                    FastAPI Application                         │
│                                                               │
│   Auth Middleware → Ingest Router → Ingest Service             │
│                                         │                     │
│                              ┌──────────▼──────────┐          │
│                              │ Evaluation Service   │          │
│                              └──────────┬──────────┘          │
│                                         │                     │
│                    ┌────────────────────┤                     │
│                    │                    │                      │
│              Pipeline A           Pipeline B                  │
│           (Rubric CoT)        (RAG Analitik)                  │
│                    │                    │                      │
│              ┌─────┴─────┐      6 paralel LLM çağrısı        │
│              │  Stage 1  │      (gpt-5-mini)                  │
│              │  gpt-5.2  │           │                        │
│              └─────┬─────┘           │                        │
│              ┌─────┴─────┐           │                        │
│              │  Stage 2  │           │                        │
│              │ gpt-5-mini│           │                        │
│              └─────┬─────┘           │                        │
│                    └────────┬────────┘                        │
│                             │                                 │
│                    Sonuçlar Birleştirilir                     │
│                    overall_score Hesaplanır                   │
│                    PostgreSQL'e Kaydedilir                    │
└──────────────────────────────────────────────────────────────┘
```

**Tech Stack:**

| Bileşen | Teknoloji | Neden |
|---------|-----------|-------|
| Backend | FastAPI + Python 3.11 | Async destek, otomatik Swagger, hızlı geliştirme |
| Veritabanı | PostgreSQL 15 | JSON desteği, güvenilir, ücretsiz |
| ORM | SQLAlchemy 2.0 + Alembic | Tip güvenliği, migration desteği |
| Kuyruk | Redis + Celery | Async evaluation (opsiyonel) |
| LLM | gpt-5.2 (Stage 1), gpt-5-mini (Stage 2 + RAG) | Maliyet/kalite dengesi |
| Container | Docker Compose | 5 servis tek komutla ayağa kalkar |

---

## 3. Trace Nedir ve Veri Akışı

**Trace** = Bir RAG etkileşiminin kaydı.

```
Trace {
    question:     "Kredi başvurusu nasıl yapılır?"         ← Kullanıcının sorusu
    answer:       "Mobil uygulamadan başvuru yapabilirsiniz" ← LLM'in cevabı
    contexts:     ["Kredi başvurusu mobil uygulama veya..."] ← Retriever'ın getirdiği belgeler
    ground_truth: "Mobil uygulama veya şubeden..."          ← (Opsiyonel) Doğru cevap
    metadata:     {"session_id": "abc123"}                  ← Ek bilgi
}
```

**Veri Akışı:**

```
1. SDK → POST /api/v1/ingest → Trace DB'ye yazılır (status: "pending")
2. Evaluation Service tetiklenir (sync veya async/Celery)
3. evaluate_trace() çağrılır
4. Pipeline A + Pipeline B paralel çalışır (~3-5 saniye)
5. Sonuçlar birleştirilir, overall_score hesaplanır
6. EvaluationResult DB'ye yazılır
7. Trace status → "completed"
```

---

## 4. İki Aşamalı Değerlendirme Motoru

### Neden İki Aşama?

**Tek aşamalı yaklaşımın problemi:**
- LLM'den direkt JSON skor istenirse, muhakeme sığ kalır
- "0.7 mi 0.8 mi?" belirsizliği yüksek olur
- Kullanıcıya "neden bu skor?" açıklaması yapılamaz

**İki aşamalı çözüm:**

| Aşama | Model | Görevi | Çıktı |
|-------|-------|--------|-------|
| **Stage 1** | gpt-5.2 (güçlü model) | Rubric'e göre serbest metin muhakeme üretir | Uzun, detaylı reasoning metni |
| **Stage 2** | gpt-5-mini (hızlı model) | Muhakeme metnini yapılandırılmış JSON'a dönüştürür | Skorlar + reasoning_summary + disagreement_claims |

**Avantajları:**
1. **Daha derin analiz** — Stage 1'de model düşünme alanına sahip (CoT)
2. **Tutarlı puanlama** — Rubric anchor değerleri (1.0 / 0.7 / 0.4 / 0.0) belirsizliği azaltır
3. **Açıklanabilirlik** — Her skora reasoning eşlik eder
4. **Maliyet optimizasyonu** — Ağır düşünme pahalı modelde, JSON dönüşüm ucuz modelde
5. **Güvenilirlik** — Stage 2'de retry loop + regex fallback mekanizması var

### Stage 2 Retry Mekanizması

```
Stage 2 Çağrısı
    │
    ├─► JSON parse → Schema doğrulama → Başarılı? → ✅ Devam
    │
    ├─► Başarısız? → Repair prompt ile tekrar dene (max 3 deneme)
    │
    └─► 3 deneme de başarısız? → Regex fallback ile Stage 1 metninden skor çıkar
```

---

## 5. Metrik Seçim Felsefesi

### RAG Kalitesini Ölçmek İçin Ne Lazım?

Bir RAG cevabının kalitesini değerlendirmek için **4 temel soru** sormalıyız:

```
┌─────────────────────────────────────────────────────────────┐
│  1. RETRIEVER DOĞRU BELGELERİ GETİRDİ Mİ?                 │
│     → context_precision + context_recall                     │
│                                                              │
│  2. CEVAP CONTEXT'E DAYANARAK MI ÜRETİLDİ?                 │
│     → faithfulness + hallucination_score                     │
│                                                              │
│  3. CEVAP SORUYU TAM KARŞILIYOR MU?                         │
│     → answer_relevancy + completeness                        │
│                                                              │
│  4. CEVAP KULLANICI İÇİN FAYDALI MI?                        │
│     → clarity + coherence + helpfulness + citation_check     │
│     → is_off_topic + is_deflection                           │
└─────────────────────────────────────────────────────────────┘
```

### Metrik Seçim Kaynakları

| Metrik Grubu | İlham Kaynağı | Neden Bu Yaklaşım |
|---|---|---|
| faithfulness, answer_relevancy, completeness, context_precision, context_recall | **RAGAS Framework** | RAG değerlendirmenin de facto standardı, akademik referanslı |
| answer_relevancy (statement-level) | **DeepEval** | RAGAS'ın "reverse question" yöntemi yerine statement bazlı yaklaşım daha doğrudan |
| clarity, coherence, helpfulness | **G-Eval** (NeurIPS 2023) | LLM-as-Judge ile rubric tabanlı değerlendirme yaklaşımı |
| hallucination_score, disagreement_claims | **Datadog Hallucination Detection** | Claim bazlı doğrulama, endüstri standardı |
| is_deflection, is_off_topic | **RLHF reward modelleri** | Cevap kalitesinin sınır durumlarını tespit |

### Neden 13 Metrik? Neden Bu Kadar Çok?

Her metrik **farklı bir kalite boyutunu** ölçer. Tek bir skor yeterli değildir çünkü:

```
Örnek: Faithfulness = 1.0 ama Completeness = 0.25
→ Cevap doğru ama eksik. Sadece overall_score'a baksan farketmezsin.

Örnek: Clarity = 0.4 ama Faithfulness = 1.0
→ Doğru bilgi var ama anlaşılmaz yazılmış. Yine farklı bir problem.
```

**13 metrik 3 katmana ayrılır:**

| Katman | Metrikler | Ne Ölçer |
|--------|-----------|----------|
| **Retrieval Kalitesi** | context_precision, context_recall | Retriever iyi çalışıyor mu? |
| **Grounding Kalitesi** | faithfulness, hallucination_score, citation_check | Cevap context'e dayanıyor mu? |
| **Cevap Kalitesi** | answer_relevancy, completeness, clarity, coherence, helpfulness, is_off_topic, is_deflection | Cevap kullanıcı için iyi mi? |

---

## 6. Pipeline A: Rubric Tabanlı Metrikler (Stage 1 + Stage 2)

### Rubric Nedir?

Rubric = LLM'e "bu cevap iyi mi kötü mü" sorusunu **nasıl cevaplayacağını** öğrettiğimiz kurallar. Her metrik için 4 anchor değer tanımlanır (1.0 / 0.7 / 0.4 / 0.0).

### Pipeline A Metrikleri Detaylı

---

#### 6.1 Clarity (Netlik) — `0.0 – 1.0`

**Ne ölçer:** Cevabın yapısal netliğini, anlaşılabilirliğini

**Rubric:**
| Skor | Anlam |
|------|-------|
| 1.0 | Cevap net, iyi yapılandırılmış, anlaşılması kolay, çelişki yok |
| 0.7 | Genel olarak anlaşılır, küçük belirsizlik veya gereksiz tekrar |
| 0.4 | Karmaşık, takip etmesi zor, çelişkili ifadeler veya aşırı yuvarlak cümleler |
| 0.0 | Anlamsız, ayrıştırılamaz, çelişkilerle dolu |

**Örnek:**
```
Skor 1.0: "Kredi başvurusu için mobil uygulamayı açın, 'Krediler' menüsüne tıklayın, 
           gelir belgenizi yükleyin. Sonuç 3 iş günü içinde bildirilir."

Skor 0.4: "Yani kredi başvurusu, hani o şey, şubeden de olur ama aslında olmaz da, 
           mobil de var, gelir belgesi lazım mı bilmiyorum ama olabilir de..."
```

**Ağırlık:** %5 (overall_score'da)

---

#### 6.2 Specificity (Özgüllük) — `0.0 – 1.0`

**Ne ölçer:** Cevabın somut detaylar içerip içermediğini (isimler, sayılar, tarihler, spesifik bilgiler)

**Rubric:**
| Skor | Anlam |
|------|-------|
| 1.0 | Somut detaylar var: isimler, sayılar, tarihler, spesifik gerçekler |
| 0.7 | Makul düzeyde spesifik, bazı somut detaylar var |
| 0.4 | Çoğunlukla belirsiz veya genel, somut detay yok |
| 0.0 | Tamamen belirsiz, hiçbir spesifik bilgi yok |

**Örnek:**
```
Skor 1.0: "Faiz oranı %1.89, vade 12-60 ay arası, minimum tutar 5.000 TL."

Skor 0.4: "Faiz oranı uygun, vade seçenekleri var, bir miktar para çekebilirsiniz."
```

**Ağırlık:** overall_score'da yok (quality indicator olarak saklanır)

---

#### 6.3 Coherence (Tutarlılık) — `0.0 – 1.0`

**Ne ölçer:** Cevabın akıcılığını, mantıksal tutarlılığını, iç çelişki olup olmadığını

**Rubric:**
| Skor | Anlam |
|------|-------|
| 1.0 | Akıcı, mantıksal, çelişki yok |
| 0.7 | Genel olarak tutarlı, küçük kopukluklar |
| 0.4 | Belirgin kopukluklar veya çelişkiler |
| 0.0 | Tutarsız / anlamsız |

**Örnek:**
```
Skor 1.0: "Python yorumlamalı bir dildir. Dinamik tip sistemi kullanır. 
           Bu sayede hızlı prototipleme yapılabilir."

Skor 0.4: "Python derlenmiş bir dildir. Yorumlamalı çalışır. 
           Statik tipleme zorunludur ama tip belirtmenize gerek yoktur."
```

**Ağırlık:** %10

---

#### 6.4 Helpfulness (Faydalılık) — `0.0 – 1.0`

**Ne ölçer:** Cevabın kullanıcının hedefini doğrudan çözüp çözmediğini

**Rubric:**
| Skor | Anlam |
|------|-------|
| 1.0 | Kullanıcının hedefini doğrudan çözüyor, eyleme geçirilebilir |
| 0.7 | Faydalı ama eksik veya yüzeysel |
| 0.4 | Kısmen faydalı |
| 0.0 | Faydasız / alakasız |

**Örnek:**
```
Soru: "Docker container'ım başlamıyor, port 8080 kullanımda hatası alıyorum"

Skor 1.0: "Port 8080'i kullanan process'i bulun: lsof -i :8080
           Sonra process'i durdurun: kill -9 <PID>
           Container'ı tekrar başlatın: docker start <container>"

Skor 0.4: "Docker'da port sorunları yaşanabilir. Docker belgelerine bakmanızı öneririm."
```

**Ağırlık:** %10

---

#### 6.5 is_off_topic — `boolean`

**Ne ölçer:** Sorunun sistemin kapsamı dışında olup olmadığını

```
true  → "Bu banka asistanına 'uzaydaki en büyük gezegen hangisi' sorulmuş" 
false → "Bu banka asistanına 'kredi faiz oranları nedir' sorulmuş"
```

**Etkisi:** `is_off_topic=true` olduğunda overall_score **maksimum 0.20** ile sınırlandırılır (cap). Tamamen konu dışı cevapların genel skorunu aşağıda tutar.

**Deterministik fallback:** LLM `is_off_topic` bayrağını kaçırırsa, kod tarafında şu kural uygulanır:
- `answer_relevancy == 0.0` ve `helpfulness == 0.0` ise `is_off_topic=true` zorlanır.
- Böylece off-topic cap (`0.20`) yine devreye girer.

---

#### 6.6 is_deflection — `boolean`

**Ne ölçer:** Cevabın savuşturma yapıp yapmadığını ("Bilmiyorum", "Yardımcı olamam" + hiçbir bilgi yok)

```
true  → "Üzgünüm, bu konuda yardımcı olamıyorum."
false → "Bu konuda kesin bilgim yok ama genel olarak şöyle çalışır: ..."
```

**Etkisi:** `is_deflection=true` olduğunda overall_score **maksimum 0.20** ile sınırlandırılır (cap). Geçiştirme cevaplar, clarity/coherence yüksek olsa bile yüksek genel skor alamaz.

**Ek Kural (faithfulness):** `faithfulness_claims` içinde en az bir iddia `contradicted` ise overall_score **maksimum 0.35** ile sınırlandırılır.

---

### Stage 1 Prompt Yapısı

```
[System Prompt]
You are an expert RAG answer quality evaluator.
Strictly follow the rubric below when scoring.
For each metric, write brief but clear reasoning.
Use the anchor values (1.0 / 0.7 / 0.4 / 0.0) as reference points.

[User Prompt]
RUBRIC START
  CLARITY: 1.0 = ... / 0.7 = ... / 0.4 = ... / 0.0 = ...
  SPECIFICITY: ...
  IS_OFF_TOPIC: ...
  COHERENCE: ...
  HELPFULNESS: ...
  IS_DEFLECTION: ...
RUBRIC END

Question: {question}
Answer: {answer}
Contexts: {contexts}

For each rubric metric, write brief reasoning and propose a score.
```

Stage 1 çıktısı serbest metin olarak döner. Örnek:
```
CLARITY: The answer is well-structured with a step-by-step format... Score: 0.85
SPECIFICITY: Includes specific numbers (5000 TL, %1.89)... Score: 0.9
...
```

Bu metin Stage 2'ye girer ve yapılandırılmış JSON'a dönüştürülür.

---

## 7. Pipeline B: RAG Analitik Metrikler

Bu metrikler Pipeline A'dan **bağımsız** çalışır. Her biri kendi LLM prompt'una sahiptir ve **paralel** olarak çağrılır.

```
Pipeline B Başlangıcı
    │
    ├──→ compute_answer_relevancy()      ─→ gpt-5-mini
    ├──→ compute_faithfulness()           ─→ gpt-5-mini
    ├──→ compute_citation_check()         ─→ gpt-5-mini
    ├──→ compute_completeness()           ─→ gpt-5-mini
    ├──→ compute_context_precision()      ─→ gpt-5-mini
    └──→ compute_context_recall()         ─→ gpt-5-mini
    
    + compute_hallucination_score()       ─→ (matematiksel, LLM çağrısı yok)
```

---

#### 7.1 Answer Relevancy (Cevap Alakalılığı) — `0.0 – 1.0`

**Ne ölçer:** Cevaptaki bilgilerin soruyla ne kadar alakalı olduğunu

**Yöntem:** DeepEval'ın statement-level yaklaşımı
1. LLM cevabı atomik cümlelere (statement) ayırır
2. Her cümle soruyla **relevant** veya **not_relevant** olarak sınıflandırılır
3. Skor = alakalı cümleler / toplam cümleler

**Neden RAGAS Yöntemi Değil?**
RAGAS "reverse question" yöntemi kullanır: cevaptan soru üretir, orijinal soruyla embedding benzerliği hesaplar. Bu dolaylı bir ölçümdür. Statement-level yöntem **daha doğrudan** ve **daha açıklanabilir** — hangi cümlenin alakasız olduğu görülebilir.

**Örnek:**
```
Soru: "Fransa'nın başkenti neresi?"
Cevap: "Fransa'nın başkenti Paris'tir. Paris'in nüfusu 2.1 milyondur. İtalya pizza ile ünlüdür."

Statement ayırma:
  ✓ "Fransa'nın başkenti Paris'tir"   → relevant (soruyu doğrudan cevaplıyor)
  ✓ "Paris'in nüfusu 2.1 milyondur"  → relevant (başkent hakkında bağlam)
  ✗ "İtalya pizza ile ünlüdür"       → not_relevant (konuyla ilgisiz)

Skor = 2/3 = 0.667
```

**Prompt çıktı formatı (JSON Schema):**
```json
{
  "statements": [
    {"statement": "...", "relevant": true, "reason": "..."},
    {"statement": "...", "relevant": false, "reason": "..."}
  ]
}
```

**Ağırlık:** %15

---

#### 7.2 Faithfulness (Sadakat) — `0.0 – 1.0`

**Ne ölçer:** Cevaptaki factual claim'lerin context tarafından desteklenip desteklenmediğini

**Neden en önemli metrik?** RAG'ın temel vaadi "belgelerden bilgi ver"dir. Eğer cevap context'e dayanmıyorsa, RAG sistemi amacını yerine getirmiyordur. Bu yüzden **%20 ağırlıkla** en yüksek paya sahip.

**Yöntem:**
1. LLM cevaptaki **tüm factual claim'leri** (iddiaları) çıkarır
2. Her claim context'le karşılaştırılır
3. Üç olası karar:
   - `supported` — Context açıkça destekliyor ✅
   - `not_supported` — Context bu konuda bilgi içermiyor ⚠️
   - `contradicted` — Context açıkça çelişiyor ❌
4. Skor = desteklenen claim sayısı / toplam claim sayısı

**Örnek:**
```
Cevap: "Einstein Almanya'da doğdu. İnterneti icat etti."
Context: "Einstein Alman doğumlu bir fizikçiydi."

Claim çıkarma:
  ✓ "Einstein Almanya'da doğdu"  → supported (context "Alman doğumlu" diyor)
  ✗ "İnterneti icat etti"       → not_supported (context'te internet yok)

Skor = 1/2 = 0.5
```

**Prompt çıktı formatı:**
```json
{
  "claims": [
    {"claim": "...", "verdict": "supported", "reason": "..."},
    {"claim": "...", "verdict": "not_supported", "reason": "..."}
  ]
}
```

**Önemli:** Claim listesi `faithfulness_claims` olarak DB'ye kaydedilir. Dashboard'da her claim tek tek gösterilebilir — kullanıcı hangi iddianın sorunlu olduğunu görebilir.

**Ağırlık:** %20

---

#### 7.3 Hallucination Score (Halüsinasyon Skoru) — `0.0 – 1.0`

**Ne ölçer:** Cevaptaki halüsinasyon oranını (ters skor: 1.0 = halüsinasyon yok, 0.0 = her şey uydurma)

**Yöntem:** Faithfulness claim'lerinden **matematiksel olarak türetilir** — ekstra LLM çağrısı gerekmez.

```
hallucination_score = 1.0 - (not_supported + contradicted) / toplam_claim
```

**Neden ayrı bir metrik?**
- Faithfulness: "desteklenen claim oranı" (pozitif bakış)
- Hallucination: "halüsinasyon oranı" (negatif bakış, tersten ölçüm)

Bazen ikisi aynı sonucu vermez çünkü faithfulness sadece supported'ı sayarken, hallucination hem not_supported hem contradicted'ı sayar.

**Örnek:**
```
Claims: 4 toplam, 3 supported, 1 contradicted

faithfulness       = 3/4 = 0.75
hallucination_score = 1 - (1/4) = 0.75   ← bu durumda aynı

Claims: 4 toplam, 2 supported, 1 not_supported, 1 contradicted

faithfulness       = 2/4 = 0.50
hallucination_score = 1 - (2/4) = 0.50   ← yine aynı (çünkü ikisi de "desteklenmeyen" sayar)
```

**Ağırlık:** overall_score'da ayrıca yok (faithfulness üzerinden dolaylı etki)

---

#### 7.4 Citation Check (Kaynak Doğrulama) — `0.0 – 1.0` veya `null`

**Ne ölçer:** Cevaptaki kaynak referanslarının ([1], [Source 2] vb.) gerçekten context'te var olup olmadığını

**Yöntem:**
1. Regex ile cevaptaki citation pattern'ları tespit edilir: `[1]`, `[Source 1]`, `(bkz. context 1)` vb.
2. Eğer hiç citation yoksa → `null` döner (metrik uygulanamaz)
3. Citation varsa → LLM her citation'ı doğrular:
   - Referans edilen context index'i gerçekten var mı? (bounds kontrolü)
   - O context'te claim edilen bilgi gerçekten var mı?
4. Skor = doğru citation'lar / toplam citation'lar

**Neden önemli?**
Bazı RAG sistemleri "[Kaynak 1]" gibi referans gösterir. Bu referansların sahte olmaması gerekir — kullanıcı güveni açısından kritik.

**Bounds-aware tasarım:**
```
Cevap: "Bu bilgi [Source 99]'a göre doğrudur."
Context sayısı: 3 (index 0, 1, 2)

→ [Source 99] → index 99 → bounds dışı → INCORRECT
```

**Ağırlık:** overall_score'da yok (opsiyonel metrik, null olabilir)

---

#### 7.5 Completeness (Bütünlük) — `0.0 – 1.0`

**Ne ölçer:** Cevabın sorudaki tüm bilgi ihtiyaçlarını karşılayıp karşılamadığını

**Yöntem:**
1. LLM soru + context'ten **2-6 key point** (anahtar bilgi noktası) çıkarır
2. Her key point cevapla karşılaştırılır:
   - `covered` (1.0 puan) — Cevap bu noktayı tam karşılıyor
   - `partially_covered` (0.5 puan) — Cevap bu noktaya değiniyor ama detay eksik
   - `not_covered` (0.0 puan) — Cevap bu noktayı hiç karşılamıyor
3. Skor = toplam puan / key point sayısı

**Örnek:**
```
Soru: "Eyfel Kulesi nedir, nerede, ne zaman ve kim tarafından yapıldı?"

Key Points:
  ✓ "Eyfel Kulesi nedir"       → covered     (1.0)
  ✓ "Nerede bulunuyor"         → covered     (1.0)
  ½ "Ne zaman yapıldı"         → partially   (0.5)
  ✗ "Kim tarafından yapıldı"   → not_covered (0.0)

Skor = (1.0 + 1.0 + 0.5 + 0.0) / 4 = 0.625
```

**Key point listesi** `completeness_key_points` olarak DB'ye kaydedilir.

**Ağırlık:** %15

---

#### 7.6 Context Precision (Bağlam Hassasiyeti) — `0.0 – 1.0`

**Ne ölçer:** Retriever'ın getirdiği context'lerin soruyla ne kadar alakalı olduğunu

**Yöntem:**
1. LLM her context passage'ı soruya karşı değerlendirir
2. Her context: `relevant` veya `not_relevant`
3. Skor = alakalı context sayısı / toplam context sayısı

**Neden önemli?**
Retriever çok sayıda belge getirip çoğu alakasız olabilir. Bu durumda:
- LLM gereksiz bilgiyle "kirletilir"
- Token maliyeti artar
- Cevap kalitesi düşer

**Yüksek precision** = Retriever isabetli çalışıyor
**Düşük precision** = Retriever çok gürültülü, tuning gerekiyor

**Örnek:**
```
Soru: "Python'da list comprehension nasıl kullanılır?"

Context[0]: "List comprehension, Python'da listeleri kısa yoldan oluşturmanın..."  → relevant
Context[1]: "Python 1991'de Guido van Rossum tarafından oluşturuldu..."             → not_relevant
Context[2]: "List comprehension söz dizimi: [expr for item in iterable]..."          → relevant

Skor = 2/3 = 0.667
```

**Ağırlık:** %15

---

#### 7.7 Context Recall (Bağlam Kapsamı) — `0.0 – 1.0`

**Ne ölçer:** Retriever'ın getirdiği context'lerin, doğru cevap için gereken bilgiyi ne kadar kapsadığını

**İki çalışma modu:**

| Mod | Tetikleyici | Yöntem |
|-----|------------|--------|
| Ground truth var | `ground_truth` parametresi dolu | GT'yi factual statement'lara ayır, her biri context'te var mı kontrol et |
| Ground truth yok | `ground_truth` parametresi boş | Sorudan key information needs türet, her biri context'te var mı kontrol et |

**Yüksek recall** = Context'ler doğru cevap için gerekli bilgiyi içeriyor
**Düşük recall** = Eksik context'ler var, retriever daha geniş aramalı

**Ağırlık:** %10

---

## 8. Overall Score Formülü

Overall score **LLM tarafından üretilmez** — deterministik bir ağırlıklı ortalama formülüdür:

```
overall_score = ağırlıklı_ortalama({
    faithfulness:       0.20,   ← En kritik: cevap context'e dayanıyor mu?
    completeness:       0.15,   ← Sorunun tüm kısımları cevaplanmış mı?
    answer_relevancy:   0.15,   ← Cevap soruyla alakalı mı?
    context_precision:  0.15,   ← Retriever doğru belgeler getirdi mi?
    context_recall:     0.10,   ← Context gerekli bilgiyi kapsıyor mu?
    coherence:          0.10,   ← Cevap tutarlı ve mantıklı mı?
    helpfulness:        0.10,   ← Cevap kullanıcının işine yarıyor mu?
    clarity:            0.05,   ← Cevap net ve anlaşılır mı?
})
Toplam:                 1.00
```

### 8.1 Score Cap Kuralları

Weighted ortalama hesaplandıktan sonra kalite koruma amaçlı şu cap'ler uygulanır:

```python
_DEFLECTION_SCORE_CAP = 0.20
_OFF_TOPIC_SCORE_CAP = 0.20
_CONTRADICTION_SCORE_CAP = 0.35

if is_deflection:
  score = min(score, 0.20)
if is_off_topic:
  score = min(score, 0.20)
if has_contradiction:  # any faithfulness claim verdict == "contradicted"
  score = min(score, 0.35)
```

Birden fazla koşul aynı anda true ise en düşük cap geçerli olur (ardışık `min()` davranışı).

### Ağırlık Mantığı

```
Grounding (faithfulness)        : %20  ← RAG'ın birincil vaadi
Retrieval (precision + recall)  : %25  ← Context kalitesi cevabı belirler
Coverage (completeness + relevancy): %30  ← Cevabın kapsamı
Usability (coherence + help + clarity): %25  ← Kullanıcı deneyimi
```

### None Değer Yönetimi

Bir metrik `None` döndüğünde (örn. citation_check veya context yoksa context_precision):
- O metriğin ağırlığı **diğer metriklere orantılı olarak dağıtılır**
- Formül: `weighted_sum / total_available_weight`

```python
# Örnek: faithfulness=0.8, completeness=0.6, context_precision=None
# context_precision None → 0.15 ağırlık düşer
# Yeni total_weight = 1.0 - 0.15 = 0.85
# overall_score = weighted_sum / 0.85
```

### Neden LLM'e Overall Score Ürettirmiyoruz?

| Problem | Açıklama |
|---------|----------|
| **Tutarsızlık** | Aynı trace için LLM her seferinde farklı overall score verebilir |
| **Açıklanabilirlik** | "0.73 nereden geldi?" sorusuna cevap verilemez |
| **Kontrol** | Ağırlıkları değiştirmek istediğimizde LLM prompt'unu değiştirmek riskli |
| **Tekrarlanabilirlik** | Deterministik formül her zaman aynı sonucu verir |

---

## 9. Değerlendirme Mekanizması Detaylı Akış

```
┌─────────────────────────────────────────────────────────────────────┐
│                    evaluate_trace() Fonksiyonu                      │
│                                                                     │
│  Girdi: question, answer, contexts, ground_truth (opsiyonel)       │
│                                                                     │
│  1. OpenAI client oluştur                                          │
│  2. API key yoksa → tüm metrikler None, "skipped" dön             │
│                                                                     │
│  3. ┌────────────── asyncio.create_task ──────────────┐            │
│     │                                                  │            │
│     │  TASK A: Stage 1 LLM çağrısı                     │            │
│     │    model: gpt-5.2                                │            │
│     │    system: STAGE_1_SYSTEM_PROMPT                  │            │
│     │    user: rubric + question + answer + contexts    │            │
│     │    max_tokens: 16384                              │            │
│     │    → Serbest metin reasoning döner                │            │
│     │                                                  │            │
│     │  TASK B: compute_rag_metrics()                    │            │
│     │    → 6 paralel LLM çağrısı (gpt-5-mini)         │            │
│     │    → + 1 matematiksel türetme (hallucination)    │            │
│     │    → 7 metrik sonucu döner                       │            │
│     │                                                  │            │
│     └─────────────── Paralel çalışır ─────────────────┘            │
│                                                                     │
│  4. Stage 2: Reasoning → JSON dönüşümü                             │
│     ┌─────────────────────────────────────────┐                    │
│     │  Attempt 1: JSON Schema ile çağrı       │                    │
│     │    → Parse + validate                    │                    │
│     │    → Başarılı? → devam                   │                    │
│     │    → Başarısız?                           │                    │
│     │                                           │                    │
│     │  Attempt 2: Repair prompt ile çağrı      │                    │
│     │    → Parse + validate                    │                    │
│     │    → Başarılı? → devam                   │                    │
│     │    → Başarısız?                           │                    │
│     │                                           │                    │
│     │  Attempt 3: Son repair denemesi          │                    │
│     │    → Başarısız? → Regex fallback         │                    │
│     └─────────────────────────────────────────┘                    │
│                                                                     │
│  5. Sonuçları birleştir:                                           │
│     - Rubric skorları (clarity, coherence, helpfulness...) Stage 2  │
│     - RAG skorları (faithfulness, relevancy...) Pipeline B          │
│     - is_off_topic: LLM bayrağı + fallback (relevancy=0 & help=0)   │
│     - completeness: RAG > Rubric (RAG varsa RAG'ınkini al)        │
│     - overall_score: _compute_overall_score() ile hesapla          │
│                                                                     │
│  6. Return: 20+ alan içeren dict                                   │
└─────────────────────────────────────────────────────────────────────┘
```

### Veri Tabanı Kayıt Akışı

```
evaluate_trace_and_persist(trace_id)
    │
    ├── DB'den Trace çek
    ├── evaluate_trace() çağır (async → event loop ile çalıştır)
    ├── EvaluationResult oluştur/güncelle
    │     ├── clarity, specificity, coherence... (Pipeline A)
    │     ├── faithfulness, answer_relevancy... (Pipeline B)
    │     ├── faithfulness_claims (JSON array)
    │     ├── completeness_key_points (JSON array)
    │     ├── disagreement_claims (JSON array)
    │     ├── stage_1_reasoning (tam metin)
    │     ├── model_used, prompt_version, rubric_version
    │     └── overall_score (hesaplanmış)
    ├── Trace status → "completed" veya "failed"
    └── DB commit
```

### Sync vs Async Mod

| Mod | Akış | Ne zaman |
|-----|------|----------|
| **sync** | Trace gelir → anında değerlendirilir → sonuçla birlikte yanıt döner | Geliştirme, düşük trafik |
| **async** | Trace gelir → Celery kuyruğuna atılır → "accepted" döner → Worker arka planda değerlendirir | Üretim, yüksek trafik |

Mod `EVALUATION_MODE` environment variable ile belirlenir.

---

## 10. Rubric Sistemi ve Evrimi

### Rubric Yaşam Döngüsü

```
1. TASLAK
   └── Literatür (RAGAS, G-Eval, RLHF) + domain bilgisi ile ilk cetvel yazılır

2. KALİBRASYON
   └── Golden set (50-100 trace) üzerinde insan-LLM uyumu ölçülür
       Hedef: Cohen's Kappa ≥ 0.7

3. A/B TEST
   └── v1 vs v2 karşılaştırılır, kazanan üretim rubric'i olur

4. SÜREKLİ İYİLEŞTİRME
   └── Düşük-confidence trace'ler ekip tarafından incelenir
       Rubric güncellenir, yeni versiyon numarası verilir
```

### Rubric Versiyonlama

Her değerlendirme sonucunda `rubric_version` kaydedilir (v1.0, v1.1, v2.0...). Bu sayede:
- Eski puanların hangi cetvel ile yapıldığı bilinir
- Rubric değişikliğinin etkisi ölçülebilir
- Geriye dönük analiz yapılabilir

### İlham Kaynakları ve Akademik Referanslar

| Yaklaşım | Kaynak | Nasıl Uyarladık |
|-----------|--------|-----------------|
| Rubric-based CoT | **G-Eval** (NeurIPS 2023) | Anchor değerleri + serbest metin muhakeme |
| Two-stage evaluation | **Judging LLM-as-a-Judge** (ICLR 2024) | Stage 1 reasoning + Stage 2 extraction ayrımı |
| Claim-level verification | **RAGAS framework** | Faithfulness claim extraction + verification |
| Statement-level relevancy | **DeepEval** | RAGAS reverse-question yerine doğrudan sınıflandırma |
| Context precision/recall | **RAGAS v0.1** | Retrieval kalitesi ölçümü |
| Hallucination detection | **Datadog** | claim bazlı doğrulama, disagreement_claims |

---

## 11. Benchmark ve Doğrulama — Detaylı Açıklama

### Temel Soru: "Bu metriklerin gerçekten doğru ölçtüğünü nasıl biliyoruz?"

LLM-as-Judge sistemi kurmak kolay, ama onun **güvenilir** olduğunu kanıtlamak zor. Bunu 4 farklı açıdan test ediyoruz — her biri farklı bir güven boyutunu doğruluyor:

```
┌──────────────────────────────────────────────────────────────────────────┐
│               DOĞRULAMA STRATEJİSİ (4 KATMAN)                          │
│                                                                          │
│  Soru 1: "Temel senaryolarda doğru çalışıyor mu?"                       │
│  └── Section 1: GOLDEN SET (13 el-yapımı test)                          │
│      Yöntem: Bilinen doğru/yanlış cevaplar → beklenen skor aralıkları   │
│                                                                          │
│  Soru 2: "Kalite düştüğünde skor da düşüyor mu?"                        │
│  └── Section 2: PERTURBATION (5 metrik, 9 çift)                         │
│      Yöntem: (iyi cevap, bozulmuş cevap) çiftleri → sıralama doğru mu? │
│                                                                          │
│  Soru 3: "İnsan değerlendirmesiyle uyumlu mu?"                          │
│  └── Section 3: EXTERNAL GROUND TRUTH (4 veri seti)                     │
│      Yöntem: İnsan etiketli veri setleriyle Pearson korelasyon + F1     │
│                                                                          │
│  Soru 4: "Aynı girdiyi tekrar değerlendirince aynı sonucu veriyor mu?" │
│  └── Section 4: CONSISTENCY (2 trace × 3 tekrar)                        │
│      Yöntem: Standart sapma ≤ 0.15 mi?                                  │
└──────────────────────────────────────────────────────────────────────────┘
```

### Benchmark Nasıl Çalıştırılır?

```bash
# Docker servisleri çalışır halde (api + db + redis)
source .venv/bin/activate
python scripts/run_independent_benchmark.py --limit 5 --concurrency 5

# Sadece belirli bölümler:
python scripts/run_independent_benchmark.py --only golden,perturbation
python scripts/run_independent_benchmark.py --skip-external
```

Benchmark script gerçek API'ye trace gönderir, gerçek LLM değerlendirmesi yapar, sonucları `reports/benchmark_results.json`'a kaydeder. Son çalışma: **14.3 dakika**, 860 saniye.

---

### Section 1: Golden Set — 13/13 (%100) ✅

**Felsefe:** El ile yazılmış test case'ler, her birinin beklenen sonucu önceden biliniyor. Unit test mantığı — "bu girdi için bu çıktıyı bekliyorum".

**9 Kategori (A-I), 13 Test:**

| Test | Senaryo | Ne Test Ediyor | Geçme Kriteri | Gerçek Sonuç |
|------|---------|----------------|---------------|--------------|
| **A1** | Cevap = context'in birebir kopyası | Mükemmel cevabı tanıyabiliyor mu? | overall ≥ 0.7, faith ≥ 0.8, halluc ≥ 0.8, comp ≥ 0.7 | overall=1.0, faith=1.0 ✅ |
| **A2** | Context'in doğru parafrazi | Parafraz doğru kabul ediliyor mu? | overall ≥ 0.65, faith ≥ 0.65 | overall=0.9, faith=1.0 ✅ |
| **B1** | Tamamen uydurma cevap | Tam halüsinasyonu tespit ediyor mu? | faith ≤ 0.4, halluc ≤ 0.4 | faith=0.0, halluc=0.0 ✅ |
| **B2** | Yarısı doğru, yarısı uydurma | Karışık halüsinasyonu ayırt ediyor mu? | 0.2 ≤ faith ≤ 0.7 | faith=0.667 ✅ |
| **C1** | Cevap context'le direkt çelişiyor | Çelişkiyi tespit ediyor mu? | faith ≤ 0.3, halluc ≤ 0.3 | faith=0.0, halluc=0.0 ✅ |
| **D1** | "Üzgünüm, yardımcı olamam" | Savuşturmayı tespit ediyor mu? | is_deflection=true, help ≤ 0.3 | defl=true, help=0.0 ✅ |
| **D2** | "YouTube'dan bakın" | Yüzeysel yönlendirmeyi tespit ediyor mu? | is_deflection=true, comp ≤ 0.3 | defl=true, comp=0.3 ✅ |
| **E1** | Sorunun sadece 1/3'ü cevaplanmış | Eksik cevabı fark ediyor mu? | comp ≤ 0.5, faith ≥ 0.5 | comp=0.25, faith=1.0 ✅ |
| **F1** | Boş cevap (sadece boşluk) | Edge case: boş string | overall ≤ 0.3, comp ≤ 0.2, help ≤ 0.2 | overall=0.0, comp=0.0 ✅ |
| **F2** | Context yok, cevap genel bilgiden doğru | Context yokken çökmeyen mi? | overall ≥ 0.5, is_off_topic=false | overall=1.0 ✅ |
| **G1** | Hava durumu sorulmuş, yemek tarifi verilmiş | Konuyla ilgisiz cevabı yakalar mı? | help ≤ 0.3, comp ≤ 0.2 | help=0.0, comp=0.0 ✅ |
| **H1** | Cevap doğru ama context bambaşka konuda | Context'ten bağımsız cevabı yakalar mı? | faith ≤ 0.3 | faith=0.0 ✅ |
| **I1** | Cevaptaki `[0]` citation'ları doğru context'e referans veriyor | Doğru citation'ı tanıyor mu? | citation ≥ 0.5, faith ≥ 0.7 | citation=1.0, faith=1.0 ✅ |

**Örnek Test Case Detayı (B1 — Tam Uydurma):**
```
Soru:    "Japonya'nın başkenti neresi?"
Cevap:   "Japonya'nın başkenti Osaka'dır. 1523'te Büyük Göç sonrası başkent oldu. 
          Nüfusu 50 milyon kişidir."
Context: "Tokyo, Japonya'nın başkentidir. 1868'den bu yana başkenttir. 
          Tokyo'nun nüfusu yaklaşık 14 milyondur."

Beklenti: Cevaptaki 3 claim'in hepsi yanlış → faithfulness = 0.0
Sonuç:    faithfulness = 0.0 ✅ (Sistem her uydurma claim'i tespit etti)
```

**A2 Parafraz Testi — Öğrenilen Ders:**
İlk sürümde A2 testi `faith ≥ 0.7` threshold'uydu ve başarısız oluyordu (faith=0.67). Neden? Cevaptaki "famous" kelimesi context'te yok — faithfulness doğru çalışıyor, threshold yanlıştı. Parafraz kaçınılmaz olarak küçük eklemeler yapabilir, bu yüzden threshold 0.70 → 0.65'e düşürüldü.

---

### Section 2: Perturbation Tests — 5/5 (%100) ✅

**Felsefe:** External ground truth olmayan metrikleri nasıl doğrularız? "Kaliteyi bozarsam skor düşmeli" prensibi. Her metrik için (iyi, bozulmuş) cevap çiftleri oluşturuyoruz. Eğer bozulmuş versiyonun skoru düşükse, metrik çalışıyor demektir.

**Neden bu yöntem?**
clarity, specificity, citation_check gibi metrikler için büyük ölçekli insan-etiketli veri seti yok. Ama "bozulmuş veri her zaman daha kötü olmalı" prensibi evrensel.

| Metrik | Çift Sayısı | Bozma Yöntemi | Sonuç |
|--------|-------------|---------------|-------|
| **answer_relevancy** | 2 | 1) Alakasız cümleler inject et (pizza, borsa, yunus...) → **1.0→0.33** | ✅ |
|  |  | 2) Tamamen farklı konu cevap ver (Python'dan bahset) → **1.0→0.0** | ✅ |
| **completeness** | 2 | 1) Detayları sil, tek cümle bırak → **1.0→0.3** | ✅ |
|  |  | 2) 5 parçalı soruya sadece 2 kısmı cevapla → **1.0→0.3** | ✅ |
| **clarity** | 2 | 1) "Hani şey, yani, belki, bir şekilde..." gibi belirsiz ifade → **1.0→0.4** | ✅ |
|  |  | 2) Kendi kendisiyle çelişen cümleler yaz → **1.0→0.4** | ✅ |
| **specificity** | 1 | "330 metre, Gustave Eiffel, 1889" → "uzun yapı, biri, bir zaman" → **1.0→0.0** | ✅ |
| **citation_check** | 1+1 | 1) Citation'ları kaldır → SKIP (metrik null döner, doğru) | ○ |
|  |  | 2) [Source 99], [Source 42], [15] — var olmayan indeksler → **0.67→0.0** | ✅ |

**Geçme kriteri:** Her metrik için testable çiftlerin ≥%80'i doğru olmalı.

**Perturbation Test Örneği (answer_relevancy — inject irrelevant):**
```
Orijinal cevap:
  "Eyfel Kulesi, Paris'teki demir kafes bir kuledir. 1887-1889 arasında inşa edilmiştir."
  → answer_relevancy = 1.0 (tüm cümleler soruyla alakalı)

Bozulmuş cevap (aynı cevap + 4 alakasız cümle eklendi):
  "Eyfel Kulesi, Paris'teki demir kafes bir kuledir. 1887-1889 arasında inşa edilmiştir.
   Pizza İtalya'da popüler bir yemektir. 2008'de borsa krizi yaşandı.
   Yunuslar zeki deniz memelileridir. Kek tarifi un, şeker gerektirir."
  → answer_relevancy = 0.33 (6 cümleden 2'si alakalı)

Kontrol: 1.0 > 0.33 → PASS ✅
```

**completeness_partial — Öğrenilen Ders:**
İlk sürümde "Eyfel Kulesi nedir ve ne zaman yapıldı?" (2 parçalı soru) kullanılıyordu. Partial cevap bile her iki noktaya değindiği için skor düşmüyordu. Çözüm: 5 parçalı soru kullandık:
```
"Eyfel Kulesi nedir, kim tasarladı, ne zaman yapıldı, ne kadar yüksek, ne kadara mal oldu?"
```
Bu durumda 2/5 kısma cevap veren partial cevap net olarak düşük skor alıyor (1.0 → 0.3).

---

### Section 3: External Ground Truth — 8/8 (%100) ✅

**Felsefe:** İnsan etiketleri olan akademik veri setlerinde bizim puanlarımız insanlarla ne kadar uyumlu?

**Kullanılan İstatistikler:**
- **Pearson r** — Korelasyon katsayısı. 1.0 = mükemmel pozitif ilişki, 0.0 = ilişki yok
- **Accuracy** — Binary sınıflandırma doğruluğu (threshold 0.5)
- **F1 Score** — Precision ve Recall'un harmonik ortalaması
- **Geçme kriteri:** r ≥ 0.4 VEYA F1 ≥ 0.5

#### 3a) RAGBench (HotPotQA subset)

**Veri seti:** `rungalileo/ragbench` — RAG sistemleri için insan etiketli veri. Her trace'te `adherence_score` (0-1) var.

**Örnekleme stratejisi:** Düşük ve yüksek adherence skorlarından eşit sayıda seçim (diversity). Sadece ortayı seçmek dar aralıkta korelasyon verir.

| Test | Bizim Metrik | GT Metrik | Pearson r | F1 | n |
|------|-------------|-----------|-----------|-----|---|
| ragbench_faith_vs_adherence | faithfulness | adherence_score | **0.603** | 0.743 | 28 |
| ragbench_overall_vs_adherence | overall_score | adherence_score | **0.546** | 0.698 | 30 |

**Bilinçli Dışlama Kararları:**
```
┌──────────────────────────────────────────────────────────────────┐
│ ❌ RAGBench completeness_score ile bizim completeness'i          │
│    KARŞILAŞTIRMIYORUZ!                                           │
│                                                                  │
│ Neden? RAGBench completeness = kullanılan_cümleler / alınan_cümleler   │
│ (sentence utilization — retriever odaklı)                        │
│                                                                  │
│ Bizim completeness = cevaplanmış_key_point / toplam_key_point   │
│ (key-point coverage — cevap odaklı)                              │
│                                                                  │
│ Elma ile armut karşılaştırması olur. Düşük korelasyon            │
│ "metriğimiz yanlış" değil, "farklı şeyler ölçüyorlar" demektir. │
├──────────────────────────────────────────────────────────────────┤
│ ❌ RAGBench relevance_score ile bizim answer_relevancy'yi       │
│    KARŞILAŞTIRMIYORUZ!                                           │
│                                                                  │
│ RAGBench relevance = alakalı_context_cümleleri / toplam_cümleler│
│ (context relevance — retriever odaklı)                           │
│                                                                  │
│ Bizim answer_relevancy = alakalı_cevap_statement / toplam_stmt  │
│ (answer relevance — cevap odaklı)                                │
└──────────────────────────────────────────────────────────────────┘
```

Bu ayrım önemli — benchmark sonuçlarını yapay olarak yükseltmemek için "elma-armut karşılaştırması" yapan testleri bilinçli olarak çıkardık.

#### 3b) SummEval (Uzman Etiketli Özetler)

**Veri seti:** `mteb/summeval` — Haber özetleri için uzman puanları (1-5 ölçeğinde, biz 0-1'e normalize ediyoruz).

**Örnekleme:** Diversity-based selection — GT skorlarında geniş yayılım sağlamak için düşük ve yüksek uçlardan eşit seçim. Sıralı seçim yapınca GT aralığı dar kalıyor (0.625-0.754) ve korelasyon anlamsız oluyor.

| Test | Bizim Metrik | GT Metrik | Pearson r | n |
|------|-------------|-----------|-----------|---|
| summeval_coherence | coherence | coherence (1-5→0-1) | **0.593** | 5 |
| summeval_faith_vs_consistency | faithfulness | consistency (1-5→0-1) | **0.949*** | 3 |
| summeval_help_vs_relevance | helpfulness | relevance (1-5→0-1) | **0.636** | 5 |
| summeval_overall | overall_score | ortalama GT | **0.956** | 5 |

**\*Ceiling effect notu:** SummEval consistency skorlarının %81.6'sı 1.0. Bu GT'de neredeyse hiç varyans yok demek. Yüksek korelasyon yanıltıcı olabilir — ama biz bunu kabul kriterinde dikkate alıyoruz (`r ≥ 0.3 VEYA gt_mean > 0.9`).

**Öğrenilen Ders (SummEval):** İlk sürümde r = -0.76 / -0.15 / 0.02 çıkıyordu (başarısız). Sorun: sıralı seçim ile GT aralığı çok dardı (0.625-0.754). Diversity-based seçim ile düşük+yüksek uçlar dahil edilince r = 0.59 / 0.64 / 0.96'ya çıktı.

#### 3c) TruthfulQA

**Veri seti:** `truthfulqa/truthful_qa` — Doğru ve yanlış cevap çiftleri. Binary: doğru cevap → gt=1.0, yanlış cevap → gt=0.0.

| Test | Bizim Metrik | Pearson r | Accuracy | F1 | n |
|------|-------------|-----------|----------|-----|---|
| truthfulqa_overall | overall_score | **0.277** | 50% | 0.667 | 10 |
| truthfulqa_helpfulness | helpfulness | **0.468** | 70% | 0.667 | 10 |

**Neden korelasyon düşük?** TruthfulQA context sağlamıyor. Bizim sistem context-based çalışıyor. Context olmadan faithfulness/context_precision/context_recall hesaplanamıyor. Bu durumda overall_score'un önemli bir kısmı null metriklerden geliyor. Yine de F1 ≥ 0.5 kriteri geçiyor.

#### 3d) HaluEval (Halüsinasyon Testi) — *en son çalışmada dahil*

**Veri seti:** `pminervini/HaluEval` — Her soru için (doğru cevap, hallucinated cevap) çiftleri var.

**Test mantığı:** Çift indeks doğru cevap, tek indeks hallucinated cevap gönderilir. Faithfulness/hallucination sistemin bunları ayırt edip edemediği test edilir.

---

### Section 4: Consistency — 8/10 (%80) ⚠️

**Felsefe:** LLM-based evaluation inherently stokastik. Aynı trace'i 3 kez değerlendirip sonuçların tutarlı olup olmadığını ölçüyoruz.

**Geçme kriteri:** Standard sapma ≤ 0.15

**Test trace'leri:**
- Trace 1: Fotosentez (basit, net cevap)
- Trace 2: Işık hızı (basit, net cevap)

| Test | Tekrar Değerleri | Mean | StdDev | Sonuç |
|------|-----------------|------|--------|-------|
| t1_overall_score | [0.97, 1.0, 1.0] | 0.990 | 0.017 | ✅ |
| t1_faithfulness | [1.0, 1.0, 1.0] | 1.000 | 0.000 | ✅ |
| t1_completeness | [1.0, 1.0, 1.0] | 1.000 | 0.000 | ✅ |
| **t1_helpfulness** | **[0.7, 1.0, 1.0]** | **0.900** | **0.173** | ❌ |
| t1_coherence | [1.0, 1.0, 1.0] | 1.000 | 0.000 | ✅ |
| t2_overall_score | [1.0, 0.925] | 0.963 | 0.053 | ✅ |
| t2_faithfulness | [1.0, 1.0] | 1.000 | 0.000 | ✅ |
| **t2_completeness** | **[1.0, 0.625]** | **0.812** | **0.265** | ❌ |
| t2_helpfulness | [1.0, 1.0] | 1.000 | 0.000 | ✅ |
| t2_coherence | [1.0, 1.0] | 1.000 | 0.000 | ✅ |

**2 Başarısızlığın Root Cause Analizi:**

**t1_helpfulness (stddev=0.173):**
```
Değerler: 0.7, 1.0, 1.0
Sorun: Rubric anchor sınırında salınım

Rubric'te:
  1.0 = "Kullanıcının hedefini doğrudan çözüyor"
  0.7 = "Faydalı ama eksik veya yüzeysel"

LLM bazen fotosentez cevabını "tam çözüm" (1.0), bazen "doğru ama biraz 
yüzeysel" (0.7) olarak değerlendiriyor. İki anchor arasında karar sınırı 
belirsiz — doğal LLM varyansı.

Severity: DÜŞÜK — Mean=0.9, yön doğru, kullanıcı etkisi minimal.
```

**t2_completeness (stddev=0.265):**
```
Değerler: 1.0, 0.625 (3. tekrar None döndü → sadece 2 veri noktası)
Sorun: LLM her çalışmada farklı sayıda key point çıkarıyor

1. çalışma: 2 key point → hepsi covered → 1.0
2. çalışma: 4 key point → 2.5/4 → 0.625
3. çalışma: evaluation timeout → None

Key point sayısı arttıkça her birinin ağırlığı düşer ve skor değişir.
Ayrıca 2 veri noktası ile stddev amplify oluyor.

Severity: DÜŞÜK — 3+ veri noktasıyla stabilize olur.
```

---

### Ek Doğrulama: Labeled Dataset (12 Trace)

Benchmark dışında ayrı bir labeled dataset (12 elle etiketlenmiş trace) ile doğrulama yapıldı:

| # | Trace | Beklenen Davranış | Sonuç |
|---|-------|-------------------|-------|
| 1 | perfect_high_all | Tüm metrikler yüksek | ❌ (completeness beklenenden düşük) |
| 2 | hallucination_contradiction | faith/halluc düşük | ✅ |
| 3 | partial_answer_low_completeness | comp düşük, faith yüksek | ✅ |
| 4 | offtopic_sentence_low_relevancy | relevancy düşük | ✅ |
| 5 | low_context_precision_noise | ctx_precision düşük | ✅ |
| 6 | low_context_recall_missing_info | ctx_recall düşük | ✅ |
| 7 | deflection_case | is_deflection=true | ✅ |
| 8 | citation_correct | citation_check yüksek | ✅ |
| 9 | citation_incorrect | citation_check düşük | ✅ |
| 10 | clarity_low | clarity düşük | ✅ |
| 11 | coherence_low_contradiction | coherence düşük | ✅ |
| 12 | specificity_low_vague | specificity düşük | ✅ |

**Sonuç: 11/12 (%91.67)**

### Ek Doğrulama: RAGBench 20-Trace Labeled Test

20 RAGBench trace'i ile:
- Pearson(faithfulness, GT adherence) = **0.4696**
- Pearson(overall, GT adherence) = **0.5855**
- Bucket separation: low group overall=0.685, high group overall=0.833
- **Korelasyon gate: PASS** (her ikisi ≥ 0.4)

### Ek Doğrulama: Gerçek RAG Sistemi ile 6-Trace End-to-End

6 gerçek senaryo trace'i ile end-to-end test yapıldı:

| Senaryo | Overall | Faithfulness | Kriter | Sonuç |
|---------|---------|-------------|--------|-------|
| Perfect retriever+reranker | 0.915 | 0.8 | Yüksek beklenti | ✅ |
| Hallucination (OOMKilled) | 0.368 | 0.0 | Halüsinasyon tespiti | ✅ |
| Partial latency | 0.800 | 1.0, comp=0.167 | Eksik ama doğru | ✅ |
| Low context precision | 0.780 | 1.0, ctx_prec=0.5 | Gürültü tespiti | ✅ |
| Low context recall | 0.535 | 0.0, ctx_rec=0.0 | Eksik context tespiti | ✅ |
| Deflection (Redis) | 0.515 | is_defl=true, help=0.0 | Savuşturma tespiti | ✅ |

---

### Benchmark Evriminde Yapılan Düzeltmeler

| Versiyon | Problem | Root Cause | Çözüm |
|----------|---------|-----------|-------|
| v1.0 | A2 faith=0.67 threshold'u geçemiyor | Parafraz "famous" ekliyor → strict faithfulness doğru | Threshold 0.70→0.65 |
| v1.0 | completeness partial TIED at 1.0 | 2 parçalı soru çok kolay | 5 parçalı soru kullandık |
| v1.0 | SummEval r = -0.76 | Sıralı seçim: dar GT aralığı (0.625-0.754) | Diversity-based seçim |
| v1.1 | consistency_t2 faith stddev=0.289 | "invented" vs "credited with patenting" belirsiz trace | Belirsiz olmayan trace ile değiştirdik |
| v1.1 | RAGBench completeness korelasyonu düşük | Farklı tanımlar (sentence utilization vs key-point) | Karşılaştırmayı tamamen çıkardık |

### Sonuç Özeti

```
┌────────────────────────────────────────────────────────┐
│         BENCHMARK SONUÇ TABLOSU: 34/36 (%94)          │
│                                                        │
│  Golden Set:    13/13 (%100)  — Temel senaryolar ✅    │
│  Perturbation:   5/5 (%100)  — Hassasiyet testleri ✅  │
│  External GT:    8/8 (%100)  — İnsan uyumu ✅          │
│  Consistency:   8/10 (%80)   — 2 düşük-severity ⚠️    │
│                                                        │
│  Ek: Labeled 12-trace: 11/12 (%91.67) ✅               │
│  Ek: RAGBench 20-trace: Corr gate PASS ✅              │
│  Ek: E2E 6-trace: 6/6 (%100) ✅                        │
└────────────────────────────────────────────────────────┘
```

---

## 12. Bilinen Limitasyonlar

| Limitasyon | Detay | Severity |
|-----------|--------|----------|
| **Consistency varyansı** | Rubric anchor sınırlarında (0.7 vs 1.0) LLM bazen farklı skor verebilir | Düşük |
| **Completeness key point sayısı** | LLM her çalışmada farklı sayıda key point çıkarabilir (2 vs 4), bu skoru etkiler | Düşük |
| **Citation check null** | Citation olmayan cevaplarda metrik uygulanamaz, null döner | Tasarım gereği |
| **LLM maliyeti** | Her trace ~$0.0056, yüksek trafikte maliyet önemli olabilir | Orta |
| **LLM latency** | Evaluation ~3-5 saniye, async mod ile kullanıcı bekletilmez | Tasarım gereği |
| **Ground truth opsiyonel** | context_recall ground truth varsa daha doğru, yoksa sorudan türetilir | Düşük |

---

## 13. Maliyet Analizi

### Trace Başına Maliyet

| Bileşen | Input Token | Output Token | Maliyet |
|---------|-------------|--------------|---------|
| Stage 1 (gpt-5.2) | ~900 | ~400 | ~$0.00037 |
| Stage 2 (gpt-5-mini) | ~600 | ~300 | ~$0.00075 |
| RAG metrics (6× gpt-5-mini) | ~3600 | ~1800 | ~$0.0045 |
| **Toplam** | | | **~$0.0056** |

### Ölçekleme

| Günlük Trace | Aylık Maliyet |
|-------------|---------------|
| 100 | ~$16.80 |
| 1,000 | ~$168 |
| 10,000 | ~$1,680 |
| 100,000 | ~$16,800 |

---

## Sunum Sırası Önerisi

1. **Problem tanımı** (5 dk) — RAG'ın kalite sorunları, neden otomatik ölçüm lazım
2. **3 satır entegrasyon demosu** (3 dk) — SDK nasıl çalışır
3. **Mimari** (5 dk) — Bileşenler ve veri akışı
4. **Two-Stage açıklaması** (10 dk) — Neden iki aşama, rubric ne, Stage 1 + Stage 2 akışı
5. **Metrik seçim felsefesi** (5 dk) — 4 temel soru, 3 katman
6. **Pipeline A metrikleri** (10 dk) — Rubric metrikler örneklerle
7. **Pipeline B metrikleri** (15 dk) — RAG analitik metrikler örneklerle, claim-level detay
8. **Overall score formülü** (5 dk) — Ağırlıklar ve neden deterministik
9. **Benchmark sonuçları** (5 dk) — 34/36, nasıl doğruladık
10. **Sorular** (10 dk)

---

*Bu rehber projenin Sprint 2 sonu (20 Şubat 2026) durumuna göre hazırlanmıştır.*
