# RAG Eval Tool - Yol Haritasi ve Sprint Plani

Toplam Sure: 4 Hafta / 4 Sprint


---

## Icindekiler

- [1. Proje Ozeti](#1-proje-ozeti)
- [2. Teknik Stack](#2-teknik-stack)
- [3. Sprint Genel Bakis](#3-sprint-genel-bakis)
- [4. Sprint 1 - Altyapi ve Temel Metrikler](#4-sprint-1---altyapi-ve-temel-metrikler)
  - [4.1 Gunluk Plan](#41-gunluk-plan)
  - [4.2 Metrikler](#42-metrikler)
  - [4.3 Teslim Edilecekler](#43-teslim-edilecekler)
- [5. Sprint 2 - RAG Metrikleri ve Async Worker](#5-sprint-2---rag-metrikleri-ve-async-worker)
  - [5.1 Gunluk Plan](#51-gunluk-plan)
  - [5.2 Eklenen Metrikler](#52-eklenen-metrikler)
  - [5.3 Teslim Edilecekler](#53-teslim-edilecekler)
- [6. Sprint 3 - Analytics API SDK ve Deploy](#6-sprint-3---analytics-api-sdk-ve-deploy)
  - [6.1 Gunluk Plan](#61-gunluk-plan)
  - [6.2 Teslim Edilecekler](#62-teslim-edilecekler)
- [7. Sprint 4 - Analytics Dashboard](#7-sprint-4---analytics-dashboard)
  - [7.1 Gunluk Plan](#71-gunluk-plan)
  - [7.2 Sayfa Yapisi](#72-sayfa-yapisi)
  - [7.3 Dashboard Dizin Yapisi](#73-dashboard-dizin-yapisi)
  - [7.4 Sayfa Mockuplari](#74-sayfa-mockuplari)
  - [7.5 Teslim Edilecekler](#75-teslim-edilecekler)
- [8. API Endpoint Tablosu](#8-api-endpoint-tablosu)
- [9. Metrik Tablosu](#9-metrik-tablosu)
- [10. Veritabani Semasi](#10-veritabani-semasi)
- [11. Proje Dizin Yapisi](#11-proje-dizin-yapisi)
- [12. Maliyet Analizi](#12-maliyet-analizi)
- [13. Sprint Kabul Kriterleri](#13-sprint-kabul-kriterleri)
- [14. V2 Backlog](#14-v2-backlog)

---

## 1. Proje Ozeti

Kullanicilar kendi RAG sistemlerine 3 satir SDK ekleyerek her soru-cevap-context etkilesiminin kalitesini otomatik olarak olcen bir SaaS evaluation platformu.

Kullanici herhangi bir dataset yuklemez. Gercek kullanimdaki her soru + cevap + context SDK araciligiyla otomatik olarak yakalanir ve iki asamali (two-stage) LLM-as-Judge yontemiyle puanlanir.

Degerlendirme Mimarisi: Rubric-based Chain-of-Thought prompting ile Stage 1 (gpt-5.2) her metrik icin puanlama cetvelini (rubric) kullanarak serbest metin muhakeme uretir, Stage 2 (gpt-5-mini) bu muhakemeyi yapilandirilmis JSON skorlara donusturur. Bu sayede daha tutarli puanlama, derin analiz, aciklanabilir sonuclar ve claim bazli dogrulama saglanir.

### Gelistirici Entegrasyonu (3 Satir)

**ONCE — Geliştiricinin mevcut RAG kodu:**

```python
# app.py  (mevcut RAG uygulamasi)
def chat(question: str) -> str:
    contexts = retriever.search(question)        # 1) Retriever contextleri getirir
    answer   = llm.generate(question, contexts)  # 2) LLM cevap uretir
    return answer
```

**SONRA — Sadece 3 satir SDK eklenir:**

```python
# app.py  (+ rageval entegrasyonu)
from rageval import RagEvalTracker                          # ← 1. satir

tracker = RagEvalTracker(api_key="sk-abc...xyz")            # ← 2. satir

def chat(question: str) -> str:
    contexts = retriever.search(question)
    answer   = llm.generate(question, contexts)
    tracker.log(question=question, answer=answer, contexts=contexts)  # ← 3. satir
    return answer
```

**Arka planda ne olur:**

```
Kullanici soru sorar
        │
        ▼
  ┌─────────────┐
  │  Retriever   │──→ contexts
  └─────────────┘
        │
        ▼
  ┌─────────────┐
  │  Generator   │──→ answer
  └─────────────┘
        │
        ▼
  ┌──────────────────────────────────────────────────┐
  │  tracker.log(question, answer, contexts)          │
  │    ├─ POST /api/v1/ingest → trace DB'ye yazilir   │
  │    ├─ Stage 1 (gpt-5.2): Rubric-based CoT         │
  │    ├─ Stage 2 (gpt-5-mini): JSON skorlama         │
  │    └─ 8 metrik + reasoning DB'ye kaydedilir        │
  └──────────────────────────────────────────────────┘
        │
        ▼
  Dashboard'da sonuclar gorunur
```

**API key'i environment variable olarak kullanma:**

```bash
# .env dosyasina ekle
RAGEVAL_API_KEY=sk-abc...xyz
```

```python
import os
from rageval import RagEvalTracker

tracker = RagEvalTracker(api_key=os.getenv("RAGEVAL_API_KEY"))
```

Not: `api_key` parametresi verilmezse SDK otomatik olarak `RAGEVAL_API_KEY` env degiskenini arar.

Not: `tracker.log()` cagrisi non-blocking (asenkron) calisir, RAG uygulamasinin yanit suresini etkilemez.

**OpenAI API Key Kullanimi:**

Gelistirici zaten kendi RAG uygulamasinda kullandigi OpenAI API key'ini ayni sekilde bizim tool icin de kullanir. Ekstra bir key almasi gerekmez.

```
Gelistiricinin Ortami
─────────────────────
.env dosyasi:
  OPENAI_API_KEY=sk-proj-xxx        ← zaten var, RAG icin kullaniyor
  RAGEVAL_API_KEY=re-abc...xyz      ← bizim platformdan alir (auth icin)

Ayni OPENAI_API_KEY hem RAG hem eval icin kullanilir:

  retriever.search(question)         → OPENAI_API_KEY ile embedding
  llm.generate(question, contexts)   → OPENAI_API_KEY ile cevap uretimi
  tracker.log(q, a, ctx)             → trace gonderir → backend OPENAI_API_KEY
                                       ile Stage 1 + Stage 2 eval yapar
```

SDK, gelistiricinin ortamindaki `OPENAI_API_KEY` env degiskenini otomatik okur ve evaluation isteginde backend'e iletir. Backend bu key ile LLM eval cagrilarini yapar.

```python
import os
from rageval import RagEvalTracker

# OPENAI_API_KEY env'den otomatik okunur (zaten mevcut)
# RAGEVAL_API_KEY env'den otomatik okunur (platformdan alinan auth key)
tracker = RagEvalTracker()

def chat(question: str) -> str:
    contexts = retriever.search(question)
    answer = llm.generate(question, contexts)
    tracker.log(question=question, answer=answer, contexts=contexts)
    return answer
```

| Key | Amac | Kim verir |
|---|---|---|
| `OPENAI_API_KEY` | LLM cagrisi (hem RAG hem eval) | Gelistiricinin kendi OpenAI hesabi |
| `RAGEVAL_API_KEY` | Bizim platforma auth (X-API-Key) | Platformumuza kayit olunca uretilir |

**Farkli model kullanilsa bile ekstra key gerekmez:**

OpenAI API key hesap bazlidir, model bazli degildir. Tek bir `OPENAI_API_KEY` tum modellere erisim saglar.

```
Gelistiricinin tek OPENAI_API_KEY'i
  │
  ├─ RAG uygulamasi  → gpt-5 (veya gpt-4o, gpt-4-turbo, vb.)
  ├─ Bizim eval tool → gpt-5.2 (Stage 1) + gpt-5-mini (Stage 2)
  │
  └─ Hepsi ayni key, ayni hesap, tek fatura
```

| Soru | Cevap |
|---|---|
| Ekip gpt-5 kullaniyor, eval tool gpt-5.2. Ekstra key gerekir mi? | **Hayir.** Ayni key tum modellere erisir |
| Farkli modeller farkli fiyatlandirilir mi? | Evet, ama hepsi ayni faturada gorunur |
| Eval maliyeti ne kadar ekler? | ~$0.00035/trace (gpt-5'e kiyasla ihmal edilebilir) |

Not: Eval maliyeti (~$0.00035/trace) gelistiricinin mevcut OpenAI faturasina yansir. Ekstra hesap veya kurulum gerekmez.

### Uc Uca Ornek: Bir Trace'in Hayat Dongusuu

Asagida gercek bir soru-cevap etkilesiminin basindan sonuna nasil degerlendirildigini adim adim gosteriyoruz.

**Senaryo:** Bir banka chatbot'u, musteri "Kredi karti limitimi nasil arttirabilirim?" diye soruyor.

---

**Adim 1 — Kullanici soru sorar, RAG sistemi cevap uretir:**

```
Kullanici: "Kredi karti limitimi nasil arttirabilirim?"

Retriever sonucu (contexts):
  [0] "Kredi karti limit artisi icin mobil uygulamadan veya 
       subeden talep olusturabilirsiniz. Minimum 6 ay musteri 
       olmak gerekir."
  [1] "Limit artis talebi kredi skoruna gore degerlendirilir. 
       Sonuc 3 is gunu icinde bildirilir."

LLM cevabi (answer):
  "Kredi karti limitinizi artirmak icin mobil uygulamadan talep 
   olusturabilirsiniz. Basvurunuz 24 saat icinde sonuclanir. 
   Ayrica subeden de islem yapabilirsiniz."
```

---

**Adim 2 — SDK trace'i yakalar ve API'ye gonderir:**

```python
tracker.log(
    question="Kredi karti limitimi nasil arttirabilirim?",
    answer="Kredi karti limitinizi artirmak icin mobil uygulamadan...",
    contexts=["Kredi karti limit artisi icin mobil...", "Limit artis talebi..."]
)
```

SDK arka planda:
```
POST /api/v1/ingest
Headers: X-API-Key: re-abc...xyz
Body: { question, answer, contexts }

→ API trace'i DB'ye kaydeder (status: "pending")
→ Evaluation baslatilir
```

---

**Adim 3 — Stage 1: gpt-5.2 Rubric-based CoT Muhakeme**

Backend soruyu + cevabi + contexti + rubric'i gpt-5.2'ye gonderir:

```
[Stage 1 Prompt ozeti]
Sen bir degerlendirme uzmanisisin. Asagidaki soru, cevap ve baglami 
rubric cetvellerine gore degerlendir. Her metrik icin adim adim 
muhakeme yap.

Soru: "Kredi karti limitimi nasil arttirabilirim?"
Cevap: "...mobil uygulamadan talep... 24 saat icinde sonuclanir... 
        subeden de islem yapabilirsiniz."
Baglam: ["...mobil uygulama veya sube...", "...3 is gunu icinde..."]

Rubric:
  completeness: 1.0=tam, 0.7=cogu, 0.4=kismi, 0.0=ilgisiz
  helpfulness:  1.0=dogrudan cozer, 0.7=eksik ama faydali...
  ...
```

gpt-5.2 serbest metin muhakeme uretir:

```
[Stage 1 Ciktisi — Serbest metin muhakeme]

CLARITY: Soru kisa, net ve anlasilir. Tek bir amac var: limit artisi. 
Puan: yuksek.

COMPLETENESS: Cevap mobil uygulama ve subeyi belirtiyor, bu dogru. 
Ancak cevap "24 saat icinde sonuclanir" diyor, baglam ise "3 is gunu 
icinde" diyor. Eksik: minimum 6 ay musteri sartindan bahsetmiyor. 
Puan: orta.

COHERENCE: Cevap mantikli bir akisla yazilmis, cumleler birbiriyle 
tutarli. Puan: yuksek.

HELPFULNESS: Mobil uygulama ve sube bilgisi faydali. Ancak sure 
bilgisi yanlis, bu kullaniciyi yaniltabilir. Puan: orta.

IS_DEFLECTION: Hayir, cevap soruyu cevaplamaya calisiyor.

HALLUCINATION ANALIZI:
- Claim 1: "Mobil uygulamadan talep olusturabilirsiniz" → Baglam 
  destekliyor ✅
- Claim 2: "24 saat icinde sonuclanir" → Baglam "3 is gunu" diyor ❌ 
  UYDURMA
- Claim 3: "Subeden de islem yapabilirsiniz" → Baglam destekliyor ✅

OVERALL: Cevap kismen faydali ama sure bilgisi uydurma.
```

---

**Adim 4 — Stage 2: gpt-5-mini JSON Skorlama**

Muhakeme metni gpt-5-mini'ye gonderilir, yapilandirilmis JSON'a donusturulur:

```json
{
  "clarity": 0.95,
  "specificity": 0.80,
  "is_off_topic": false,
  "completeness": 0.55,
  "coherence": 0.90,
  "helpfulness": 0.60,
  "is_deflection": false,
  "overall_score": 0.65,
  "evaluation_confidence": 0.88,
  "reasoning_summary": "Cevap dogru yonlendirme yapiyor ancak sure bilgisi baglama aykiri (3 is gunu yerine 24 saat) ve musteri sartindan bahsetmiyor.",
  "disagreement_claims": [
    {
      "claim": "Basvuru 24 saat icinde sonuclanir",
      "context_says": "Sonuc 3 is gunu icinde bildirilir",
      "type": "contradiction"
    },
    {
      "claim": "Minimum musteri suresi gerekliligi",
      "context_says": "Minimum 6 ay musteri olmak gerekir",
      "type": "missing_info"
    }
  ]
}
```

---

**Adim 5 — Skorlar DB'ye kaydedilir:**

```
evaluation_results tablosu:
  trace_id:        "abc-123"
  clarity:          0.95
  specificity:      0.80
  completeness:     0.55
  coherence:        0.90
  helpfulness:      0.60
  overall_score:    0.65
  is_off_topic:     false
  is_deflection:    false
  evaluation_confidence: 0.88
  reasoning_summary: "Cevap dogru yonlendirme yapiyor ancak..."
  disagreement_claims: [{claim: "24 saat", ...}]
  stage_1_reasoning: "CLARITY: Soru kisa, net..."
  model_used:       "gpt-5.2 + gpt-5-mini"
  prompt_version:   "v1.0"
  rubric_version:   "v1.0"

traces tablosu:
  status: "pending" → "completed"
```

---

**Adim 6 — Dashboard'da gorunum:**

```
┌──────────────────────────────────────────────────────────┐
│  TRACE DETAIL — abc-123                                   │
│                                                           │
│  Soru: "Kredi karti limitimi nasil arttirabilirim?"       │
│  Cevap: "...mobil uygulamadan talep... 24 saat icinde..." │
│                                                           │
│  ┌──────────── SKORLAR ─────────────┐                    │
│  │ clarity:      █████████░  0.95   │                    │
│  │ coherence:    █████████░  0.90   │                    │
│  │ specificity:  ████████░░  0.80   │                    │
│  │ overall:      ██████░░░░  0.65   │                    │
│  │ helpfulness:  ██████░░░░  0.60   │                    │
│  │ completeness: █████░░░░░  0.55   │  ← Dusuk!         │
│  │ off_topic:    Hayir ✅           │                    │
│  │ deflection:   Hayir ✅           │                    │
│  └──────────────────────────────────┘                    │
│                                                           │
│  ⚠️ Uyumsuzluk Tespit Edildi:                            │
│  ┌──────────────────────────────────────────────┐        │
│  │ ❌ "24 saat icinde sonuclanir"                │        │
│  │    Baglam: "3 is gunu icinde bildirilir"      │        │
│  │    Tip: contradiction (celiskili bilgi)        │        │
│  │                                               │        │
│  │ ⚠️ Eksik bilgi: minimum 6 ay musteri sarti    │        │
│  │    Tip: missing_info                          │        │
│  └──────────────────────────────────────────────┘        │
│                                                           │
│  Gerekce: "Cevap dogru yonlendirme yapiyor ancak sure    │
│  bilgisi baglama aykiri ve musteri sartindan bahsetmiyor" │
└──────────────────────────────────────────────────────────┘
```

---

**Ozet — Bir trace'in 6 adimi:**

```
Kullanici sorar → RAG cevap uretir → SDK yakalar → Stage 1 muhakeme 
→ Stage 2 JSON skorlama → Dashboard'da gosterilir
```

| Adim | Ne olur | Sure |
|---|---|---|
| 1. RAG cevap uretir | Retriever + Generator | ~1-2 sn (RAG'in islemi) |
| 2. SDK trace gonderir | HTTP POST /ingest | ~50 ms |
| 3. Stage 1 muhakeme | gpt-5.2 rubric CoT | ~2-3 sn |
| 4. Stage 2 JSON | gpt-5-mini formatlama | ~1 sn |
| 5. DB kayit | Skorlar + reasoning yazilir | ~10 ms |
| 6. Dashboard | Kullanici sonucu gorur | anlik |

---

## 2. Teknik Stack

| Katman | Teknoloji |
|---|---|
| Backend | FastAPI (Python 3.11+) |
| Veritabani | PostgreSQL 15, SQLAlchemy 2.0, Alembic |
| Validation | Pydantic v2 |
| LLM | OpenAI gpt-5.2 (Stage 1 Rubric-based CoT) + gpt-5-mini (Stage 2 JSON) |
| Embeddings | sentence-transformers (Sprint 2) |
| Async Queue | Redis + Celery (Sprint 2) |
| Frontend | Next.js 14, Tailwind CSS, shadcn/ui, Recharts (Sprint 4) |
| SDK | Python package (rageval) |
| Container | Docker + Docker Compose |
| Test | pytest + httpx |

---

## 3. Sprint Genel Bakis

| Sprint | Hafta | Hedef | Cikti |
|---|---|---|---|
| S1 | 1 | Altyapi + LLM Eval | API calisiyor, trace gonder, 8 metrik puanla |
| S2 | 2 | RAG Metrikleri + Async | Faithfulness, Hallucination, batch eval, Celery worker |
| S3 | 3 | Analytics API + SDK + Deploy | 6 analytics endpoint, pip install rageval, Docker deploy |
| S4 | 4 | Analytics Dashboard | Web dashboard, grafikler, filtreler, canli izleme |

---

## 4. Sprint 1 - Altyapi ve Temel Metrikler

Hedef: API ayaga kalksin, trace kabul etsin, LLM ile 8 temel metrik puanlasin.

Eval Modu: Senkron. Redis ve Celery bu sprintte kullanilmaz.

### 4.1 Gunluk Plan

Gun 1 - Pazartesi - Proje Kurulumu ve Veritabani

| Gorev |
|---|
| Proje iskeleti: dizin yapisi, requirements.txt |
| .env ve config.py (environment variables) |
| Docker Compose: api + postgres servisleri |
| SQLAlchemy engine, session, Base kurulumu (database.py) |
| Alembic init ve ilk migration |
| User, Trace, EvaluationResult modelleri |

Beklenen cikti: docker-compose up ile PostgreSQL ve API calisiyor, tablolar hazir.

Gun 2 - Sali - Auth ve Ingest API

| Gorev |
|---|
| Pydantic schemas: auth.py, ingest.py |
| POST /api/v1/auth/register (email + password, API key uret) |
| API key servisi: token uretimi ve sha256 hash |
| Auth middleware: X-API-Key header dogrulama |
| POST /api/v1/ingest (tek trace kaydet) |
| POST /api/v1/ingest/batch (toplu trace kaydet) |
| GET /api/v1/traces (listeleme, pagination) |
| GET /api/v1/traces/{id} (tek trace detay) |

Beklenen cikti: Kayit ol, API key al, trace gonder, listele.

Gun 3 - Carsamba - LLM Client ve Two-Stage Evaluation Engine

| Gorev |
|---|
| llm_client.py: OpenAI async wrapper, retry, hata yonetimi |
| Stage 1 prompt: Rubric-based CoT ile her metrik icin puanlama cetvelini kullanarak serbest metin muhakeme ureten prompt (gpt-5.2) |
| Stage 2 prompt: Muhakeme metnini 8 metrik + reasoning + disagreement_claims JSON a donusturen prompt (gpt-5-mini) |
| evaluator.py: evaluate_trace() fonksiyonu (iki asamali cagri) |
| Ingest sonrasi otomatik evaluation, sonucu (skorlar + reasoning) DB ye kaydet |
| GET /api/v1/traces/{id} evaluation sonucu + reasoning_summary ile birlikte donsun |

Two-Stage Evaluation Akisi:
```
Asama 1: Question + Context + Answer + Rubric → gpt-5.2 → Rubric-based serbest metin muhakeme
Asama 2: Muhakeme metni → gpt-5-mini → Yapilandirilmis JSON (skorlar + reasoning + claims)
```

Beklenen cikti: Trace gonder, LLM iki asamada puanlasin, 8 metrik skoru + aciklama donsun.

Gun 4 - Persembe - Test ve Hata Yonetimi

| Gorev |
|---|
| Unit testler: auth, ingest, evaluation servisleri |
| Integration test: register, ingest, evaluate, sonuc kontrol |
| Golden set regression test: sabit 50-100 trace ile skor tutarliligi kontrol |
| Hata yonetimi: LLM timeout, rate limit, JSON parse |
| Structured logging (request_id bazli) |
| Edge case: bos soru, cok uzun cevap, eksik alan |

Beklenen cikti: Testler yesil, hata durumlari ele alinmis.

Gun 5 - Cuma - Sprint Review ve Duzeltmeler

| Gorev |
|---|
| Bug fix: test sonuclarina gore duzeltmeler |
| OpenAPI/Swagger dokumantasyonu |
| Postman/curl ile demo senaryosu hazirla |
| Sprint review ve retrospektif |

Beklenen cikti: Sprint 1 tamamlandi, demo hazir.

### 4.2 Metrikler

Iki asamali Rubric-based CoT ile tum metrikler puanlanir. Stage 1 (gpt-5.2) her metrik icin puanlama cetvelini (rubric) kullanarak serbest metin muhakeme uretir, Stage 2 (gpt-5-mini) bu muhakemeyi yapilandirilmis JSON'a donusturur.

| No | Metrik | Tip | Aciklama |
|---|---|---|---|
| 1 | clarity | 0.0 - 1.0 | Soru anlasilir mi |
| 2 | specificity | 0.0 - 1.0 | Soru yeterince spesifik mi |
| 3 | is_off_topic | bool | Soru kapsam disi mi |
| 4 | completeness | 0.0 - 1.0 | Cevap soruyu tam karsiliyor mu |
| 5 | coherence | 0.0 - 1.0 | Cevap mantikli ve tutarli mi |
| 6 | helpfulness | 0.0 - 1.0 | Cevap kullaniciya faydali mi |
| 7 | is_deflection | bool | Sistem soruyu savusturuyor mu |
| 8 | overall_score | 0.0 - 1.0 | Genel kalite puani |

### 4.2.1 Rubric Sablonlari (Ornek)

**completeness**
- 1.0: Sorudaki tum alt sorular/talepler eksiksiz cevaplanmis
- 0.7: Sorunun buyuk kismi cevaplanmis, 1-2 nokta eksik
- 0.4: Sorunun sadece bir kismi cevaplanmis
- 0.0: Cevap soruyla ilgisiz veya bos

**helpfulness**
- 1.0: Cevap kullanici hedefini dogrudan cozer, uygulanabilir
- 0.7: Faydalı ama eksik/ustunkoru
- 0.4: Kismen alakali fakat yeterince faydali degil
- 0.0: Faydasiz veya alakasiz

**is_deflection**
- true: “Bu konuda yardimci olamiyorum”, “bilmiyorum”, konu disina kacma
- false: Soruyu cevaplama niyeti var ve icerik sunuyor

Not: Her evaluation sonucu icin `prompt_version` ve `rubric_version` alanlari DB'ye yazilarak izlenebilirlik saglanacak.

### 4.2.2 Rubric Nasil Belirleniyor?

Rubric'ler (puanlama cetvelleri) sabit degil, sistematik bir surecle olusturulur ve zamanla evrilir.

**Kaynak: Akademik literatur + endustri standartlari**

Metrikler ve puanlama seviyeleri su kaynaklardan turetilmistir:

| Metrik | Ilham Kaynagi |
|---|---|
| completeness | RAGAS (Retrieval Augmented Generation Assessment) frameworku |
| coherence | G-Eval (NLG kalite degerlendirme) yaklasimi |
| helpfulness | RLHF (Reinforcement Learning from Human Feedback) reward modelleri |
| is_off_topic | Intent classification literaturunden |
| is_deflection | Chatbot UX arastirmalarindan |
| clarity / specificity | Soru kalitesi degerlendirme literaturunden |
| disagreement_claims | Datadog LLM Hallucination Detection yaklasimi (claim bazli dogrulama) |

**Surecin 4 adimi:**

```
Adim 1: Taslak Rubric Olusturma
  ↓
  Literatur + domain bilgisi ile ilk rubric'ler yazilir
  Ornek: completeness icin 4 kademe (1.0, 0.7, 0.4, 0.0) 
  ve her kademe icin acik, somut tanim

Adim 2: Golden Set ile Kalibrasyon
  ↓
  50-100 ornek trace (soru + cevap + context) uzerinde:
  - Insan degerlendirici 3 kisi bagimsiz puanlar
  - LLM ayni trace'leri rubric'e gore puanlar
  - Insan-LLM uyumu olculur (Cohen's Kappa >= 0.7 hedef)
  
  Dusuk uyum olan metriklerde rubric ifadeleri netlestirilir.
  Ornek: "buyuk kismi cevaplanmis" belirsiz → 
         "sorudaki 3+ alt konudan en az 2'si cevaplanmis" gibi
         somut hale getirilir.

Adim 3: A/B Test ile Dogrulama
  ↓
  Rubric v1 vs v2 ayni trace setinde karsilastirilir:
  - Hangi versiyon insan puanlarina daha yakin?
  - Hangi versiyonda LLM daha tutarli? (ayni soruya 
    tekrar sorulunca ayni puani veriyor mu?)
  
  Kazanan versiyon uretim rubric'i olur.

Adim 4: Surekli Iyilestirme
  ↓
  Uretim verileri birikince:
  - Dusuk evaluation_confidence skorlu trace'ler ekip tarafindan incelenir
  - Kullanici geri bildirimi (thumbs up/down) rubric'i dogrudan 
    degistirmez, sadece "ekibin nereye bakmasi gerektigini" gosterir
  - Ekip inceleme sonucunda rubric ifadelerini gunceller
  - rubric_version arttirilir (v1.0 → v1.1 → v2.0)
  - Eski versiyonla puanlanan trace'ler karsilastirma icin saklanir
  
  Not: Rubric evrimi otonom degil, ekip-gudumlududur. Kullanici 
  geri bildirimi bir onceliklendirme sinyalidir, otomatik 
  rubric degisikligi tetiklemez.
```

**Rubric prompt'a nasil gomiluyor?**

Rubric dogrudan Stage 1 system prompt'unun icine yerlestirilir:

```
[System Prompt - Stage 1]

Sen bir RAG cevap kalitesi degerlendirme uzmanisisin.
Asagidaki soru, cevap ve baglami her metrik icin
verilen puanlama cetvelini kullanarak degerlendir.

--- RUBRIC BASLANGIC ---

COMPLETENESS:
  1.0 = Sorudaki tum alt sorular/talepler eksiksiz cevaplanmis
  0.7 = Sorunun buyuk kismi cevaplanmis, 1-2 nokta eksik
  0.4 = Sorunun sadece bir kismi cevaplanmis
  0.0 = Cevap soruyla ilgisiz veya bos

HELPFULNESS:
  1.0 = Cevap kullanici hedefini dogrudan cozer, uygulanabilir
  0.7 = Faydali ama eksik/ustunkoru
  0.4 = Kismen alakali fakat yeterince faydali degil
  0.0 = Faydasiz veya alakasiz

COHERENCE:
  1.0 = Cumleler mantikli siralanmis, celiskisiz, akici
  0.7 = Genel olarak tutarli, kucuk kopukluklar var
  0.4 = Bazi cumleler birbiriyle celisiyor veya kopuk
  0.0 = Anlamsiz veya tamamen tutarsiz

CLARITY:
  1.0 = Soru net, tek anlamli, anlasilir
  0.7 = Anlasilir ama biraz belirsiz
  0.4 = Birden fazla anlama gelebilir
  0.0 = Anlamsiz veya parse edilemez

SPECIFICITY:
  1.0 = Somut, olculebilir, dar kapsamli soru
  0.7 = Makul duzeyde spesifik
  0.4 = Genis/genel bir soru
  0.0 = Anlamsiz derecede belirsiz

IS_OFF_TOPIC:
  true  = Soru sistemin kapsam alaniyla ilgisiz
  false = Soru kapsam dahilinde

IS_DEFLECTION:
  true  = Cevap "bilmiyorum", "yardimci olamiyorum" gibi 
          savusturma iceriyor ve bilgi sunmuyor
  false = Soruyu cevaplama niyeti var, icerik sunuyor

HALLUCINATION ANALIZI:
  Cevaptaki her factual claim'i baglamdaki bilgiyle karsilastir:
  - supported:     Baglam dogrudan destekliyor ✅
  - contradiction: Baglam farkli/celiskili bilgi veriyor ❌
  - missing_info:  Baglam bu konuda bilgi icermiyor ⚠️
  - fabricated:    Baglamda hic olmayan detay uydurulmus ❌

--- RUBRIC BITIS ---

Simdi asagidaki trace'i degerlendir:
Soru: {question}
Cevap: {answer}
Baglam: {contexts}

Her metrik icin adim adim muhakeme yap.
```

**Neden sabit seviyeler (1.0 / 0.7 / 0.4 / 0.0)?**

LLM'lerin 0-1 arasinda surekli skor vermesi tutarsizdir (ayni cevaba bir seferinde 0.72, digerine 0.68 verebilir). Sabit anchor noktlari (1.0, 0.7, 0.4, 0.0) kullanmak:
- LLM'in karar uzayini daraltir → daha tutarli puanlama
- Insan kalibrasyonunu kolaylastirir (4 kademe vs sonsuz skala)
- Gercek cikti yine de 0.0-1.0 arasi olabilir (LLM "0.7 ile 0.4 arasi, 0.55" diyebilir) ama anchor'lar rehber gorevi gorur

**Rubric versiyonlama:**

```
rubric_versions tablosu:
  version:    "v1.0"
  created_at: "2026-02-15"
  metrics:    {completeness: {...}, helpfulness: {...}, ...}
  changelog:  "Ilk versiyon"

  version:    "v1.1"  
  created_at: "2026-03-01"
  metrics:    {completeness: {0.7 ifadesi guncellendi}, ...}
  changelog:  "completeness 0.7 seviyesi netlesti: '3+ alt 
               konudan en az 2si cevaplanmis' eklendi"
```

Her evaluation sonucunda `rubric_version` alani saklanir, boylece zaman icinde rubric degisse bile eski puanlamalarin hangi cetvel ile yapildigini biliyoruz.

Ek Alanlar (Two-Stage ciktisi):

| Alan | Tip | Aciklama |
|---|---|---|
| reasoning_summary | string | Puanlamanin tek cumlelik gerekce ozeti |
| disagreement_claims | JSON array | Context-cevap uyumsuzluk analizi (claim bazli) |
| stage_1_reasoning | text | Stage 1 serbest metin muhakeme (ham cikti) |
| evaluation_confidence | float | Skor guven puani (0.0-1.0) |

### 4.3 Teslim Edilecekler

- [ ] FastAPI projesi + Docker Compose (API + PostgreSQL)
- [ ] User, Trace, EvaluationResult modelleri + migration
- [ ] POST /api/v1/auth/register
- [ ] Auth middleware (X-API-Key)
- [ ] POST /api/v1/ingest (tek trace + senkron eval)
- [ ] POST /api/v1/ingest/batch (toplu trace)
- [ ] GET /api/v1/traces (pagination)
- [ ] GET /api/v1/traces/{id} (detay + evaluation)
- [ ] Two-Stage LLM-as-Judge evaluator (Stage 1: gpt-5.2 Rubric-based CoT, Stage 2: gpt-5-mini JSON skorlama)
- [ ] reasoning_summary ve disagreement_claims ciktisi
- [ ] Rate limiting + basic quota (kullanici bazli gunluk limit)
- [ ] Unit ve Integration testler
- [ ] Swagger/OpenAPI dokumantasyonu

---

## 5. Sprint 2 - RAG Metrikleri ve Async Worker

Hedef: Faithfulness ve Hallucination metrikleri ekle, async evaluation, batch file upload.

Yeni Bilesen: Redis + Celery ekleniyor.

### 5.1 Gunluk Plan

Gun 1 - Pazartesi - Redis ve Celery Kurulumu

| Gorev |
|---|
| Docker Compose'a redis servisi ekle |
| celery_app.py, worker konfigurasyon |
| evaluate_trace_async.delay(trace_id) taski |
| Ingest akisini syncten asynce cevir |
| GET /api/v1/traces/{id}/status (pending/processing/completed) |

Beklenen cikti: Trace gonder, Celery worker arka planda degerlendirsin.

Gun 2 - Sali - Answer Relevancy ve Faithfulness

| Gorev |
|---|
| Answer Relevancy: sentence-transformers ile embedding similarity |
| all-MiniLM-L6-v2 modeli yukleme ve cache |
| Faithfulness: LLM ile claim extraction, her claimi contextte dogrula |
| Faithfulness skoru: dogrulanan / toplam claim orani |

Beklenen cikti: 2 yeni RAG-spesifik metrik calisiyor.

Gun 3 - Carsamba - Hallucination ve Citation Check

| Gorev |
|---|
| Hallucination Detection: contextte olmayan iddialari tespit et |
| Hallucination skoru: uydurma iddia sayisi / toplam iddia |
| Citation Check: citation taglerini context ile karsilastir |
| Deflection Rate: aggregate deflection orani hesaplama |

Beklenen cikti: 3 yeni metrik daha, toplam 13 metrik.

Gun 4 - Persembe - Batch File Upload ve Test

| Gorev |
|---|
| (Opsiyonel) POST /api/v1/ingest/upload (CSV/JSON dosya kabul) |
| (Opsiyonel) Parser: CSV ve JSON format destegi |
| (Opsiyonel) Upload sonrasi Celery ile toplu eval |
| Yeni metrikler ve async flow icin testler |

Beklenen cikti: Dosya upload et, toplu degerlendir.

Gun 5 - Cuma - Sprint Review ve Stabilizasyon

| Gorev |
|---|
| Bug fix, edge case: buyuk dosya, timeout, worker crash |
| Retry mekanizmasi: basarisiz evalleri tekrar dene |
| rawdata.json ile 500 kayit toplu test (demo) |
| Sprint review ve retrospektif |

Beklenen cikti: Sprint 2 tamamlandi, 13 metrik + async + batch.

### 5.2 Eklenen Metrikler

| No | Metrik | Tip | Yontem |
|---|---|---|---|
| 9 | answer_relevancy | 0.0 - 1.0 | Embedding similarity (sentence-transformers) |
| 10 | faithfulness | 0.0 - 1.0 | LLM claim extraction + context dogrulama |
| 11 | hallucination | 0.0 - 1.0 | Context disi iddia tespiti |
| 12 | citation_check | 0.0 - 1.0 | Citation tag ve context eslestirme |
| 13 | deflection_rate | 0.0 - 1.0 | Toplam deflection / toplam trace orani |

### 5.3 Teslim Edilecekler

- [ ] Redis + Celery worker entegrasyonu
- [ ] Async evaluation (arka plan isleme)
- [ ] Trace status endpoint (pending/completed)
- [ ] Answer Relevancy metrigi
- [ ] Faithfulness metrigi
- [ ] Hallucination Detection metrigi
- [ ] Citation Check metrigi
- [ ] (Opsiyonel) POST /api/v1/ingest/upload (dosya upload)
- [ ] (Opsiyonel) Batch processing (Celery ile toplu eval)
- [ ] Retry mekanizmasi
- [ ] Testler (async flow + yeni metrikler)

---

## 6. Sprint 3 - Analytics API SDK ve Deploy

Hedef: Analytics endpointleri, Python SDK paketi, production Docker deploy.

Cikti: Backend tamamen hazir, SDK ile entegrasyon mumkun.

### 6.1 Gunluk Plan

Gun 1 - Pazartesi - Analytics: Summary ve Trends

| Gorev |
|---|
| GET /api/v1/analytics/summary?period=7d |
| Aggregation servisi: ortalama skor, deflection rate, kalite dagilimi |
| GET /api/v1/analytics/trends?period=30d&granularity=daily |
| Time series query: gunluk, haftalik, aylik aggregation |

Beklenen cikti: Ozet istatistikler ve zaman bazli trend verisi.

Gun 2 - Sali - Analytics: Worst Traces, Distribution, Deflections, Compare

| Gorev |
|---|
| GET /api/v1/analytics/worst-traces?limit=10 |
| GET /api/v1/analytics/distribution?metric=helpfulness |
| GET /api/v1/analytics/deflections (konu bazli analiz) |
| GET /api/v1/analytics/compare?period_a=X&period_b=Y |

Beklenen cikti: 6 analytics endpoint tam calisiyor.

Gun 3 - Carsamba - Python SDK + PyPI Yayinlama

| Gorev |
|---|
| rageval paketi: __init__.py, client.py, tracker.py |
| RagEvalTracker: tracker.log(question, answer, contexts) |
| SDK ozellikleri: retry, batch buffer, error callback |
| pyproject.toml: paket adi, versiyon, bagimliliklar, metadata |
| README.md (SDK): kurulum, hizli baslangic, API referans |
| PyPI'ye yayinlama: twine ile upload (TestPyPI ile test sonrasi) |
| Versiyon stratejisi: semantic versioning (0.1.0 ile baslat) |
| SDK unit test ve entegrasyon testi |

PyPI Yayinlama Akisi:
```
1. TestPyPI'ye yukle ve test et:
   pip install build twine
   python -m build
   twine upload --repository testpypi dist/*
   pip install --index-url https://test.pypi.org/simple/ rageval

2. Test basarili → gercek PyPI'ye yukle:
   twine upload dist/*

3. Kullanici kurar:
   pip install rageval
```

pyproject.toml ornegi:
```toml
[project]
name = "rageval"
version = "0.1.0"
description = "RAG evaluation SDK - 3 satir ile otomatik kalite olcumu"
readme = "README.md"
requires-python = ">=3.9"
license = {text = "MIT"}
authors = [{name = "RAG Eval Team"}]
keywords = ["rag", "evaluation", "llm", "quality"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
    "Programming Language :: Python :: 3",
]
dependencies = [
    "httpx>=0.25.0",
    "pydantic>=2.0.0",
]

[project.urls]
Homepage = "https://github.com/your-org/rageval"
Documentation = "https://docs.rageval.dev"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Beklenen cikti: `pip install rageval` ile PyPI'den kurulum calisiyor, 3 satir entegrasyon hazir.

Gun 4 - Persembe - Docker Deploy ve Production Config

| Gorev |
|---|
| Production Dockerfile: multi-stage build, gunicorn |
| Docker Compose prod: API + PostgreSQL + Redis + Celery |
| .env.production, secret management |
| GET /health endpoint, Docker healthcheck |

Beklenen cikti: docker-compose prod ile production ortami ayaga kalkiyor.

Gun 5 - Cuma - E2E Test ve Sprint Review

| Gorev |
|---|
| E2E test: SDK ile ingest, eval, analytics akisi |
| Performans testi: 500 trace toplu, response time olcumu |
| README.md: kurulum, kullanim, API dokumantasyonu |
| Sprint review ve retrospektif |

Beklenen cikti: Backend tamamen hazir, SDK calisiyor, deploy edilebilir.

### 6.2 Teslim Edilecekler

- [ ] GET /api/v1/analytics/summary
- [ ] GET /api/v1/analytics/trends
- [ ] GET /api/v1/analytics/worst-traces
- [ ] GET /api/v1/analytics/distribution
- [ ] GET /api/v1/analytics/deflections
- [ ] GET /api/v1/analytics/compare
- [ ] Python SDK (rageval paketi)
- [ ] PyPI'ye yayinlama (pip install rageval)
- [ ] SDK README.md (kurulum + hizli baslangic + API referans)
- [ ] Production Docker Compose
- [ ] Health check endpoint
- [ ] E2E test senaryosu
- [ ] README.md ve API dokumantasyonu

---

## 7. Sprint 4 - Analytics Dashboard

Hedef: Web dashboard ile tum metrikleri gorsellestirecek, filtreleyecek ve canli izleyecek arayuz.

Cikti: Kullanici dostu dashboard, grafikler, filtreler, canli izleme.

### 7.1 Gunluk Plan

Gun 1 - Pazartesi - Proje Kurulumu ve Layout

| Gorev |
|---|
| Next.js 14 projesi olustur (App Router) |
| Tailwind CSS + shadcn/ui kurulumu |
| Layout: sidebar, header, main content alani |
| Auth sayfasi: login formu, API key ile giris |
| API client: backend baglantisi, token yonetimi |

Beklenen cikti: Dashboard iskeleti hazir, login calisiyor.

Gun 2 - Sali - Overview ve Traces Sayfalari

| Gorev |
|---|
| Overview sayfasi: summary kartlari, trend grafigi (Recharts) |
| KPI kartlari: toplam trace, ort. skor, deflection rate, kalite dagilimi |
| Traces sayfasi: tablo, pagination, arama, siralama |
| Trace detay modal/sayfasi: tum metrikler, soru-cevap, context |

Beklenen cikti: Ana sayfa grafikleri ve trace listesi calisiyor.

Gun 3 - Carsamba - Analytics ve Filtreler

| Gorev |
|---|
| Analytics sayfasi: metrik dagilim grafikleri (histogram, bar chart) |
| Worst traces tablosu: en dusuk skorlu trace listesi |
| Tarih filtresi: 7d, 30d, 90d, custom range |
| Metrik filtresi: dropdown ile metrik secimi |
| Karsilastirma sayfasi: iki donem yan yana |

Beklenen cikti: Filtreleme ve analitik gorsellemeler calisiyor.

Gun 4 - Persembe - Canli Izleme ve Polish

| Gorev |
|---|
| Live feed: son gelen trace lerin canli akisi (polling/SSE) |
| Deflection analiz sayfasi: konu bazli deflection grafigi |
| Responsive tasarim: mobil ve tablet uyumu |
| Loading states, error states, empty states |
| Dark mode destegi |

Beklenen cikti: Canli izleme calisiyor, UX tamamlandi.

Gun 5 - Cuma - Test, Deploy ve Sprint Review

| Gorev |
|---|
| Component testleri (Jest + React Testing Library) |
| E2E test: login, dashboard goruntuleme, filtreleme |
| Docker ile frontend deploy (Nginx) |
| Docker Compose guncelleme: frontend servisi ekle |
| Sprint review ve retrospektif |

Beklenen cikti: Dashboard deploy edildi, tum sprintler tamamlandi.

### 7.2 Sayfa Yapisi

| Sayfa | Route | Aciklama |
|---|---|---|
| Login | /login | API key ile giris |
| Overview | /dashboard | KPI kartlari, trend grafigi, ozet |
| Traces | /dashboard/traces | Trace listesi, arama, pagination |
| Trace Detail | /dashboard/traces/[id] | Tek trace detayi, tum metrikler |
| Analytics | /dashboard/analytics | Metrik dagilim, histogram, filtreler |
| Worst Traces | /dashboard/worst-traces | En dusuk skorlu trace ler |
| Deflections | /dashboard/deflections | Konu bazli deflection analizi |
| Compare | /dashboard/compare | Donem karsilastirma |
| Live Feed | /dashboard/live | Canli trace akisi |
| Settings | /dashboard/settings | API key yonetimi, profil |

### 7.3 Dashboard Dizin Yapisi

```
dashboard/
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   ├── login/
│   │   └── page.tsx
│   └── dashboard/
│       ├── layout.tsx
│       ├── page.tsx                  # Overview
│       ├── traces/
│       │   ├── page.tsx              # Trace listesi
│       │   └── [id]/
│       │       └── page.tsx          # Trace detay
│       ├── analytics/
│       │   └── page.tsx
│       ├── worst-traces/
│       │   └── page.tsx
│       ├── deflections/
│       │   └── page.tsx
│       ├── compare/
│       │   └── page.tsx
│       ├── live/
│       │   └── page.tsx
│       └── settings/
│           └── page.tsx
├── components/
│   ├── ui/                           # shadcn/ui bilesenler
│   ├── layout/
│   │   ├── Sidebar.tsx
│   │   ├── Header.tsx
│   │   └── MainContent.tsx
│   ├── charts/
│   │   ├── TrendChart.tsx
│   │   ├── DistributionChart.tsx
│   │   ├── MetricBarChart.tsx
│   │   └── CompareChart.tsx
│   ├── cards/
│   │   ├── KPICard.tsx
│   │   └── MetricCard.tsx
│   ├── tables/
│   │   ├── TraceTable.tsx
│   │   └── WorstTracesTable.tsx
│   └── filters/
│       ├── DateFilter.tsx
│       └── MetricFilter.tsx
├── lib/
│   ├── api.ts                        # API client
│   ├── auth.ts                       # Auth helper
│   └── utils.ts
├── hooks/
│   ├── useTraces.ts
│   ├── useAnalytics.ts
│   └── useLiveFeed.ts
├── types/
│   └── index.ts
├── tailwind.config.ts
├── next.config.js
├── package.json
└── Dockerfile
```

### 7.4 Sayfa Mockuplari

Overview Sayfasi:
```
┌─────────────────────────────────────────────────────┐
│  SIDEBAR  │          OVERVIEW DASHBOARD              │
│           │                                          │
│  Overview │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐   │
│  Traces   │  │Total │ │ Avg  │ │Defl. │ │Quality│   │
│  Analytics│  │Traces│ │Score │ │Rate  │ │ Good  │   │
│  Worst    │  │1,234 │ │ 0.78 │ │ 12%  │ │  82%  │   │
│  Deflect. │  └──────┘ └──────┘ └──────┘ └──────┘   │
│  Compare  │                                          │
│  Live     │  ┌──────────────────────────────────┐   │
│  Settings │  │     Trend Chart (30 gun)          │   │
│           │  │     ~~~~~~~~~~~~~~~~~~~~~~~~      │   │
│           │  │     overall_score line chart      │   │
│           │  └──────────────────────────────────┘   │
│           │                                          │
│           │  ┌───────────────┐ ┌────────────────┐   │
│           │  │ Son Trace ler │ │ Worst 5 Traces │   │
│           │  │ trace list... │ │ low scores...  │   │
│           │  └───────────────┘ └────────────────┘   │
└─────────────────────────────────────────────────────┘
```

Trace Detay Sayfasi:
```
┌─────────────────────────────────────────────────────┐
│  TRACE DETAIL - trace_abc123                         │
│                                                      │
│  Soru: "Kredi karti limiti nasil arttirilir?"        │
│  Cevap: "Kredi karti limitinizi artirmak icin..."    │
│  Context: ["Musteri hizmetleri...", "Limit..."]      │
│                                                      │
│  ┌─────────────── METRIKLER ───────────────────┐    │
│  │ clarity:     ████████░░  0.82                │    │
│  │ specificity: ███████░░░  0.71                │    │
│  │ completeness:█████████░  0.90                │    │
│  │ coherence:   ████████░░  0.85                │    │
│  │ helpfulness: ███████░░░  0.75                │    │
│  │ overall:     ████████░░  0.81                │    │
│  │ off_topic:   Hayir  ✅                       │    │
│  │ deflection:  Hayir  ✅                       │    │
│  └──────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

### 7.5 Teslim Edilecekler

- [ ] Next.js 14 projesi + Tailwind + shadcn/ui
- [ ] Login sayfasi (API key auth)
- [ ] Overview dashboard (KPI kartlari + trend grafigi)
- [ ] Traces listesi (pagination, arama, siralama)
- [ ] Trace detay sayfasi (tum metrikler)
- [ ] Analytics sayfasi (dagilim grafikleri, filtreler)
- [ ] Worst traces tablosu
- [ ] Deflection analiz sayfasi
- [ ] Donem karsilastirma sayfasi
- [ ] Canli trace izleme (Live Feed)
- [ ] Responsive tasarim + dark mode
- [ ] Frontend Docker deploy
- [ ] Component ve E2E testler

---

## 8. API Endpoint Tablosu

| # | Method | Endpoint | Sprint | Aciklama |
|---|---|---|---|---|
| 1 | POST | /api/v1/auth/register | S1 | Kullanici kaydi, API key uretimi |
| 2 | POST | /api/v1/ingest | S1 | Tek trace gonderimi + senkron eval |
| 3 | POST | /api/v1/ingest/batch | S1 | Toplu trace gonderimi |
| 4 | GET | /api/v1/traces | S1 | Trace listeleme (pagination) |
| 5 | GET | /api/v1/traces/{id} | S1 | Trace detay + evaluation sonucu |
| 6 | GET | /api/v1/traces/{id}/status | S2 | Async eval durumu (pending/processing/completed) |
| 7 | POST | /api/v1/ingest/upload | S2 | CSV/JSON dosya upload + toplu eval |
| 8 | GET | /api/v1/analytics/summary | S3 | Ozet istatistikler (ort. skor, toplam trace, vb.) |
| 9 | GET | /api/v1/analytics/trends | S3 | Zaman bazli trend verisi (gunluk/haftalik/aylik) |
| 10 | GET | /api/v1/analytics/worst-traces | S3 | En dusuk skorlu trace listesi |
| 11 | GET | /api/v1/analytics/distribution | S3 | Metrik dagilim verisi (histogram) |
| 12 | GET | /api/v1/analytics/deflections | S3 | Konu bazli deflection analizi |
| 13 | GET | /api/v1/analytics/compare | S3 | Iki donem karsilastirmasi |
| 14 | GET | /health | S3 | Sistem saglik kontrolu |

Tum endpointler (register ve health haric) X-API-Key header gerektirir.

Query parametreleri:
- `period`: 7d, 30d, 90d (analytics endpointleri)
- `granularity`: daily, weekly, monthly (trends)
- `limit`: sonuc sayisi siniri (worst-traces)
- `metric`: metrik adi (distribution)
- `page`, `per_page`: pagination (traces)

---

## 9. Metrik Tablosu

### Sprint 1 - Temel Metrikler (Two-Stage LLM-as-Judge)

Stage 1 (gpt-5.2, Rubric-based CoT) puanlama cetvelini kullanarak serbest metin muhakeme uretir, Stage 2 (gpt-5-mini) yapilandirilmis JSON'a donusturur.

| No | Metrik | Tip | Kaynak | Aciklama |
|---|---|---|---|---|
| 1 | clarity | 0.0 - 1.0 | Two-Stage LLM | Soru anlasilir mi |
| 2 | specificity | 0.0 - 1.0 | Two-Stage LLM | Soru yeterince spesifik mi |
| 3 | is_off_topic | bool | Two-Stage LLM | Soru kapsam disi mi |
| 4 | completeness | 0.0 - 1.0 | Two-Stage LLM | Cevap soruyu tam karsiliyor mu |
| 5 | coherence | 0.0 - 1.0 | Two-Stage LLM | Cevap mantikli ve tutarli mi |
| 6 | helpfulness | 0.0 - 1.0 | Two-Stage LLM | Cevap kullaniciya faydali mi |
| 7 | is_deflection | bool | Two-Stage LLM | Sistem soruyu savusturuyor mu |
| 8 | overall_score | 0.0 - 1.0 | Two-Stage LLM | Genel kalite puani |

Ek ciktilar: reasoning_summary (gerekce ozeti), disagreement_claims (claim bazli uyumsuzluk analizi)

### Sprint 2 - RAG Metrikleri

| No | Metrik | Tip | Kaynak | Aciklama |
|---|---|---|---|---|
| 9 | answer_relevancy | 0.0 - 1.0 | Embedding | Soru-cevap benzerlik skoru (sentence-transformers) |
| 10 | faithfulness | 0.0 - 1.0 | LLM | Cevabin contexte sadakati (claim dogrulama orani) |
| 11 | hallucination | 0.0 - 1.0 | LLM | Context disi uydurma iddia orani |
| 12 | citation_check | 0.0 - 1.0 | LLM | Citation tagleri ile context eslestirme orani |
| 13 | deflection_rate | 0.0 - 1.0 | Aggregate | Toplam deflection / toplam trace orani |

Puanlama notu: Tum 0.0-1.0 metriklerinde 1.0 en iyi, 0.0 en kotu skordur. Hallucination metriginde 0.0 hallucination yok (iyi), 1.0 tamamen uydurma (kotu) anlamina gelir.

---

## 10. Veritabani Semasi

### users Tablosu

| Sutun | Tip | Kisitlama | Aciklama |
|---|---|---|---|
| id | UUID | PK, default uuid4 | Kullanici benzersiz kimlik |
| email | VARCHAR(255) | UNIQUE, NOT NULL | Kullanici e-posta adresi |
| hashed_password | VARCHAR(255) | NOT NULL | bcrypt ile hashlanmis sifre |
| api_key_hash | VARCHAR(64) | UNIQUE, NOT NULL | SHA-256 ile hashlanmis API key |
| api_key_prefix | VARCHAR(8) | NOT NULL | API key on eki (gosterim icin) |
| is_active | BOOLEAN | DEFAULT true | Hesap aktif mi |
| created_at | TIMESTAMP | DEFAULT now() | Kayit tarihi |
| updated_at | TIMESTAMP | DEFAULT now() | Son guncelleme |

### traces Tablosu

| Sutun | Tip | Kisitlama | Aciklama |
|---|---|---|---|
| id | UUID | PK, default uuid4 | Trace benzersiz kimlik |
| user_id | UUID | FK -> users.id, NOT NULL | Trace sahibi |
| question | TEXT | NOT NULL | Kullanicinin sordugu soru |
| answer | TEXT | NOT NULL | RAG sisteminin verdigi cevap |
| contexts | JSON | NULLABLE | Retrieval sonucu context listesi |
| metadata | JSON | NULLABLE | Ek bilgi (model, session_id, vb.) |
| status | VARCHAR(20) | DEFAULT 'pending' | Eval durumu: pending/processing/completed/failed |
| created_at | TIMESTAMP | DEFAULT now() | Trace olusturma tarihi |

### evaluation_results Tablosu

| Sutun | Tip | Kisitlama | Aciklama |
|---|---|---|---|
| id | UUID | PK, default uuid4 | Sonuc benzersiz kimlik |
| trace_id | UUID | FK -> traces.id, UNIQUE, NOT NULL | Iliskili trace |
| clarity | FLOAT | NULLABLE | Soru netlik skoru (0.0-1.0) |
| specificity | FLOAT | NULLABLE | Soru spesifiklik skoru (0.0-1.0) |
| is_off_topic | BOOLEAN | NULLABLE | Kapsam disi mi |
| completeness | FLOAT | NULLABLE | Cevap tamligi (0.0-1.0) |
| coherence | FLOAT | NULLABLE | Cevap tutarliligi (0.0-1.0) |
| helpfulness | FLOAT | NULLABLE | Cevap faydasi (0.0-1.0) |
| is_deflection | BOOLEAN | NULLABLE | Savusturma var mi |
| overall_score | FLOAT | NULLABLE | Genel kalite (0.0-1.0) |
| evaluation_confidence | FLOAT | NULLABLE | Skor guven puani (0.0-1.0) |
| answer_relevancy | FLOAT | NULLABLE | Soru-cevap benzerlik (Sprint 2) |
| faithfulness | FLOAT | NULLABLE | Contexte sadakat (Sprint 2) |
| hallucination | FLOAT | NULLABLE | Uydurma iddia orani (Sprint 2) |
| citation_check | FLOAT | NULLABLE | Citation dogrulama (Sprint 2) |
| reasoning_summary | TEXT | NULLABLE | Puanlamanin tek cumlelik gerekce ozeti |
| disagreement_claims | JSON | NULLABLE | Context-cevap uyumsuzluk analizi (claim bazli) |
| stage_1_reasoning | TEXT | NULLABLE | Stage 1 Rubric-based CoT muhakeme (ham cikti) |
| raw_response | JSON | NULLABLE | Stage 2 LLM ham JSON yaniti |
| evaluated_at | TIMESTAMP | DEFAULT now() | Degerlendirme tarihi |
| model_used | VARCHAR(50) | NULLABLE | Kullanilan LLM modeli |
| prompt_version | VARCHAR(50) | NULLABLE | Kullanilan prompt/rubric versiyonu |
| rubric_version | VARCHAR(50) | NULLABLE | Kullanilan rubric versiyonu |

### Iliskiler

```
users (1) ──────< (N) traces (1) ──────< (1) evaluation_results
         one-to-many              one-to-one
```

### Indexler

| Tablo | Index | Sutunlar | Aciklama |
|---|---|---|---|
| users | ix_users_email | email | Hizli email sorgusu |
| users | ix_users_api_key_hash | api_key_hash | Auth dogrulama |
| traces | ix_traces_user_id | user_id | Kullanici trace listesi |
| traces | ix_traces_created_at | created_at | Zaman bazli sorgular |
| traces | ix_traces_status | status | Durum filtreleme |
| evaluation_results | ix_eval_trace_id | trace_id | Trace-eval eslestirme |
| evaluation_results | ix_eval_overall | overall_score | Worst traces sorgusu |

---

## 11. Proje Dizin Yapisi

```
llm-evaluation/
├── docker-compose.yml                # Dev: api + postgres
├── docker-compose.prod.yml           # Prod: api + postgres + redis + celery + frontend
├── Dockerfile                        # API multi-stage build
├── .env                              # Environment variables (dev)
├── .env.production                   # Environment variables (prod)
├── .gitignore
├── requirements.txt                  # Python bagimliliklari
├── alembic.ini                       # Alembic konfigurasyon
├── README.md
├── RAG_EVAL_TOOL_PLAN.md
│
├── alembic/
│   ├── env.py
│   └── versions/                     # Migration dosyalari
│
├── app/
│   ├── __init__.py
│   ├── main.py                       # FastAPI app, router mount
│   ├── config.py                     # Pydantic Settings, env okuma
│   ├── database.py                   # SQLAlchemy engine, session, Base
│   │
│   ├── models/                       # SQLAlchemy ORM modelleri
│   │   ├── __init__.py
│   │   ├── user.py                   # User modeli
│   │   ├── trace.py                  # Trace modeli
│   │   └── evaluation.py            # EvaluationResult modeli
│   │
│   ├── schemas/                      # Pydantic schemalar
│   │   ├── __init__.py
│   │   ├── auth.py                   # RegisterRequest, RegisterResponse
│   │   ├── ingest.py                 # TraceCreate, TraceBatch, TraceResponse
│   │   ├── evaluation.py            # EvaluationResponse
│   │   └── analytics.py             # Summary, Trends, Distribution vb.
│   │
│   ├── routers/                      # FastAPI route handlers
│   │   ├── __init__.py
│   │   ├── auth.py                   # /api/v1/auth/*
│   │   ├── ingest.py                 # /api/v1/ingest/*
│   │   ├── traces.py                 # /api/v1/traces/*
│   │   ├── analytics.py             # /api/v1/analytics/*
│   │   └── health.py                # /health
│   │
│   ├── services/                     # Is mantigi katmani
│   │   ├── __init__.py
│   │   ├── auth_service.py          # Kullanici kayit, API key islemleri
│   │   ├── ingest_service.py        # Trace kaydetme, batch islem
│   │   ├── evaluation_service.py    # Evaluator orkestrasyon
│   │   └── analytics_service.py     # Aggregation sorgulari
│   │
│   ├── evaluation/                   # Degerlendirme motoru
│   │   ├── __init__.py
│   │   ├── evaluator.py             # evaluate_trace() ana fonksiyon (two-stage)
│   │   ├── llm_client.py            # OpenAI async wrapper, retry
│   │   ├── prompts.py               # Stage 1 (Rubric-based CoT) ve Stage 2 (JSON) prompt sablonlari
│   │   └── metrics.py               # Metrik hesaplama yardimcilari
│   │
│   ├── middleware/                    # Middleware katmani
│   │   ├── __init__.py
│   │   └── auth.py                   # X-API-Key dogrulama
│   │
│   └── utils/                        # Yardimci fonksiyonlar
│       ├── __init__.py
│       ├── logging.py               # Structured logging
│       └── helpers.py               # Genel yardimcilar
│
├── worker/                           # Celery worker (Sprint 2)
│   ├── __init__.py
│   ├── celery_app.py                # Celery konfigurasyon
│   └── tasks.py                     # Async evaluation taskleri
│
├── sdk/                              # Python SDK (Sprint 3)
│   ├── rageval/
│   │   ├── __init__.py
│   │   ├── client.py                # HTTP client
│   │   └── tracker.py              # RagEvalTracker sinifi
│   ├── setup.py
│   ├── pyproject.toml
│   └── tests/
│       └── test_tracker.py
│
├── dashboard/                        # Next.js Frontend (Sprint 4)
│   └── (yapisi bolum 7.3 te)
│
└── tests/
    ├── __init__.py
    ├── conftest.py                   # Fixtures, test DB setup
    ├── test_auth.py
    ├── test_ingest.py
    ├── test_evaluation.py
    ├── test_traces.py
    ├── test_analytics.py
    └── test_e2e.py
```

---

## 12. Maliyet Analizi

### OpenAI API Maliyeti (gpt-5.2 + gpt-5-mini)

| Model | Kalem | Birim Fiyat | Aciklama |
|---|---|---|---|
| gpt-5.2 | Input tokens | $0.15 / 1M token | Stage 1: Rubric + soru + cevap + context |
| gpt-5.2 | Output tokens | $0.60 / 1M token | Stage 1: Rubric-based muhakeme |
| gpt-5-mini | Input tokens | $0.50 / 1M token | Stage 2: Muhakeme metni |
| gpt-5-mini | Output tokens | $1.50 / 1M token | Stage 2: JSON skorlama |

Iki asamali Rubric-based CoT degerlendirme:
- Stage 1 Input: ~900 token (rubric + soru + cevap + context) — gpt-5.2
- Stage 1 Output: ~400 token (rubric-based muhakeme) — gpt-5.2
- Stage 2 Input: ~600 token (muhakeme metni) — gpt-5-mini
- Stage 2 Output: ~300 token (yapilandirilmis JSON + reasoning + claims) — gpt-5-mini
- Toplam maliyet/trace: ~$0.00035

| Aylik Hacim | Trace/Ay | Tahmini Maliyet |
|---|---|---|
| Dusuk | 1,000 | ~$0.35 |
| Orta | 10,000 | ~$3.50 |
| Yuksek | 100,000 | ~$35.00 |
| Cok Yuksek | 1,000,000 | ~$350.00 |

### 12.1 SLO (Latency ve Maliyet Hedefleri)

| SLO | Hedef | Not |
|---|---|---|
| Eval latency p95 (S1, senkron) | < 5 sn | Two-Stage LLM cagrisi dahil |
| Eval latency p95 (S2, async) | < 30 sn | Kuyruk + worker dahil |
| API response p95 (non-eval) | < 300 ms | Auth, traces list, analytics sorgulari |
| Maliyet/trace (S1) | <= $0.00035 | Rubric-based CoT two-stage |
| Maliyet/trace (S2) | <= $0.0005 | Ek claim extraction dahil |

### Sprint 2 Ek Maliyetler

Faithfulness ve Hallucination icin ek LLM cagrisi:
- Claim extraction: ~500 token input, ~300 token output
- Ek maliyet/trace: ~$0.00026
- Sprint 2 ile toplam maliyet/trace: ~$0.0005

### Altyapi Maliyeti (Aylik Tahmin)

| Bilesen | Servis | Tahmini Maliyet |
|---|---|---|
| API Server | VPS / Cloud Run | $10 - $50 |
| PostgreSQL | Managed DB / Self-hosted | $0 - $25 |
| Redis | Managed / Self-hosted | $0 - $15 |
| Domain + SSL | Cloudflare | $0 - $10 |

| Senaryo | Toplam Aylik Maliyet |
|---|---|
| Hobi (1K trace, self-hosted) | ~$10 |
| Startup (10K trace, cloud) | ~$50 |
| Buyume (100K trace, cloud) | ~$150 |
| Enterprise (1M trace, cloud) | ~$400 |

---

## 13. Sprint Kabul Kriterleri

### Sprint 1 - Altyapi ve Temel Metrikler

- [ ] `docker-compose up` ile API ve PostgreSQL basariyla ayaga kalkiyor
- [ ] POST /api/v1/auth/register ile kullanici kaydi yapilabiliyor, API key donuyor
- [ ] API key olmadan endpointlere erisim 401 donuyor
- [ ] POST /api/v1/ingest ile tek trace gonderilebiliyor
- [ ] POST /api/v1/ingest/batch ile toplu trace gonderilebiliyor
- [ ] Trace gonderildikten sonra two-stage evaluation ile 8 metrik senkron olarak puanlaniyor
- [ ] Stage 1 (gpt-5.2) Rubric-based CoT muhakeme + Stage 2 (gpt-5-mini) yapilandirilmis JSON akisi calisiyor
- [ ] reasoning_summary ve disagreement_claims evaluation sonucunda donuyor
- [ ] evaluation_confidence (0.0-1.0) skoru evaluation sonucunda donuyor
- [ ] Kullanici bazli rate limiting ve gunluk quota uygulanabiliyor
- [ ] GET /api/v1/traces ile pagination calisarak trace listesi donuyor
- [ ] GET /api/v1/traces/{id} ile evaluation sonucu + reasoning dahil trace detayi donuyor
- [ ] Tum unit testler basariyla geciyor
- [ ] Integration test: register -> ingest -> evaluate -> sonuc kontrol akisi calisiyor
- [ ] LLM hata durumlari (timeout, rate limit, invalid JSON) ele alinmis
- [ ] Swagger/OpenAPI dokumanina /docs adresinden erisilebiliyor

### Sprint 2 - RAG Metrikleri ve Async Worker

- [ ] Redis ve Celery worker Docker Compose ile ayaga kalkiyor
- [ ] Trace gonderimi artik async: evaluation arka planda yapiliyor
- [ ] GET /api/v1/traces/{id}/status ile eval durumu (pending/processing/completed) izlenebiliyor
- [ ] answer_relevancy metrigi embedding similarity ile hesaplaniyor
- [ ] faithfulness metrigi claim extraction + dogrulama ile calisiyor
- [ ] hallucination metrigi context disi iddialari tespit ediyor
- [ ] citation_check metrigi citation taglerini dogruluyor
- [ ] POST /api/v1/ingest/upload ile CSV/JSON dosya yuklenebiliyor
- [ ] Yuklenenen dosya Celery ile toplu degerlendiriliyor
- [ ] Basarisiz evaluation taskleri otomatik retry ediliyor
- [ ] 500 kayitlik toplu test basariyla tamamlaniyor

### Sprint 3 - Analytics API + SDK + Deploy

- [ ] 6 analytics endpoint dogru veri donduruyor
- [ ] summary: ortalama skor, toplam trace, deflection rate
- [ ] trends: gunluk/haftalik/aylik granularity destegi
- [ ] worst-traces: en dusuk skorlu trace listesi
- [ ] distribution: metrik bazinda histogram verisi
- [ ] deflections: konu bazli deflection analizi
- [ ] compare: iki donem karsilastirmasi
- [ ] `pip install rageval` ile SDK kurulabiliyor
- [ ] SDK ile 2 satir kodla trace gonderilebiliyor
- [ ] Production Docker Compose ile tum servisler ayaga kalkiyor
- [ ] /health endpoint 200 donuyor
- [ ] E2E test: SDK -> ingest -> eval -> analytics akisi calisiyor
- [ ] README.md kurulum ve kullanim dokumani hazir

### Sprint 4 - Analytics Dashboard

- [ ] Login sayfasi calisiyor, API key ile giris yapilabiliyor
- [ ] Overview sayfasi: KPI kartlari ve trend grafigi gosteriliyor
- [ ] Traces sayfasi: tablo, pagination, arama calisiyor
- [ ] Trace detay: tum metrikler gorsellestiriliyor
- [ ] Analytics: dagilim grafikleri ve filtreler calisiyor
- [ ] Worst traces tablosu calisiyor
- [ ] Deflection analiz sayfasi calisiyor
- [ ] Donem karsilastirma calisiyor
- [ ] Canli trace izleme calisiyor
- [ ] Responsive tasarim (mobil + tablet)
- [ ] Dark mode calisiyor
- [ ] Frontend Docker ile deploy edilebiliyor
- [ ] Tum sprintler tamamlandi, sistem uretim ortamina hazir

---

## 14. V2 Backlog

Asagidaki ozellikler V1 kapsaminda degildir. Gelecek surumler icin planlanmistir.

### Kullanici Yonetimi
- [ ] Coklu kullanici ve takim destegi
- [ ] Rol bazli erisim kontrolu (RBAC): admin, viewer, editor
- [ ] OAuth2 / SSO entegrasyonu (Google, GitHub)
- [ ] Organizasyon ve proje bazli izolasyon

### Gelismis Metrikler
- [ ] Custom metrik tanimlama (kullanici kendi metrigini yazsin)
- [ ] Toxicity / safety detection
- [ ] Latency tracking (RAG sistem yanit suresi)
- [ ] Context relevancy metrigi (retrieval kalitesi)
- [ ] Kullanici geri bildirimi (thumbs up/down) entegrasyonu

### Bildirim ve Alarm
- [ ] Skor esik degeri alarmlari (orn: overall < 0.5 ise uyar)
- [ ] Slack / Email / Webhook bildirim entegrasyonu
- [ ] Anomali tespiti (ani kalite dususu)
- [ ] Gunluk/haftalik ozet rapor e-postasi

### SDK Genisletme
- [ ] JavaScript/TypeScript SDK
- [ ] Go SDK
- [ ] LangChain callback handler entegrasyonu
- [ ] LlamaIndex callback entegrasyonu
- [ ] OpenTelemetry trace destegi

### Veri ve Gizlilik
- [ ] PII (kisisel veri) maskeleme
- [ ] Veri saklama suresi politikasi (data retention)
- [ ] GDPR uyumlu veri silme
- [ ] Veri export (CSV/JSON bulk download)

### Performans ve Olceklenme
- [ ] Rate limiting (kullanici bazli)
- [ ] Caching katmani (Redis)
- [ ] Veritabani partitioning (zaman bazli)
- [ ] Horizontal scaling: coklu worker, load balancer
- [ ] Kubernetes (K8s) deploy destegi

### A/B Test ve Karsilastirma
- [ ] Model karsilastirma: farkli LLM modellerini yan yana degerlendir
- [ ] Prompt versiyonlama ve karsilastirma
- [ ] RAG pipeline A/B testi

### Diger
- [ ] Webhook: evaluation tamamlandiginda disariya bildirim
- [ ] Public API dokumantasyonu (Redoc)
- [ ] Multi-language destegi (Turkce, Almanca, vb.)
- [ ] On-premise kurulum rehberi
