# RAG Eval Tool - Yol Haritasi ve Sprint Plani

Son Guncelleme: 10 Subat 2026
Toplam Sure: 4 Hafta / 4 Sprint
Sprint Suresi: 5 is gunu (Pazartesi - Cuma)

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

Kullanicilar kendi RAG sistemlerine 2 satir SDK ekleyerek her soru-cevap etkilesiminin kalitesini otomatik olarak olcen bir SaaS evaluation platformu.

Kullanici herhangi bir dataset yuklemez. Gercek kullanimdaki her soru-cevap cifti SDK araciligiyla otomatik olarak yakalanir ve LLM-as-Judge yontemiyle puanlanir.

---

## 2. Teknik Stack

| Katman | Teknoloji |
|---|---|
| Backend | FastAPI (Python 3.11+) |
| Veritabani | PostgreSQL 15, SQLAlchemy 2.0, Alembic |
| Validation | Pydantic v2 |
| LLM | OpenAI gpt-4o-mini (LLM-as-Judge) |
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

Gun 3 - Carsamba - LLM Client ve Evaluation Engine

| Gorev |
|---|
| llm_client.py: OpenAI async wrapper, retry, hata yonetimi |
| Evaluation prompt: 8 metrigi tek seferde puanlayan JSON prompt |
| evaluator.py: evaluate_trace() fonksiyonu |
| Ingest sonrasi otomatik evaluation, sonucu DB ye kaydet |
| GET /api/v1/traces/{id} evaluation sonucuyla birlikte donsun |

Beklenen cikti: Trace gonder, LLM puanlasin, 8 metrik skoru donsun.

Gun 4 - Persembe - Test ve Hata Yonetimi

| Gorev |
|---|
| Unit testler: auth, ingest, evaluation servisleri |
| Integration test: register, ingest, evaluate, sonuc kontrol |
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

Tek bir LLM cagrisiyla tum metrikler puanlanir.

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

### 4.3 Teslim Edilecekler

- [ ] FastAPI projesi + Docker Compose (API + PostgreSQL)
- [ ] User, Trace, EvaluationResult modelleri + migration
- [ ] POST /api/v1/auth/register
- [ ] Auth middleware (X-API-Key)
- [ ] POST /api/v1/ingest (tek trace + senkron eval)
- [ ] POST /api/v1/ingest/batch (toplu trace)
- [ ] GET /api/v1/traces (pagination)
- [ ] GET /api/v1/traces/{id} (detay + evaluation)
- [ ] LLM-as-Judge evaluator (gpt-4o-mini, 8 metrik)
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
| POST /api/v1/ingest/upload (CSV/JSON dosya kabul) |
| Parser: CSV ve JSON format destegi |
| Upload sonrasi Celery ile toplu eval |
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
- [ ] POST /api/v1/ingest/upload (dosya upload)
- [ ] Batch processing (Celery ile toplu eval)
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

Gun 3 - Carsamba - Python SDK

| Gorev |
|---|
| rageval paketi: __init__.py, client.py, tracker.py |
| RagEvalTracker: tracker.log(question, answer, contexts) |
| SDK ozellikleri: retry, batch buffer, error callback |
| SDK unit test ve entegrasyon testi |

Beklenen cikti: pip install rageval ile 2 satir entegrasyon calisiyor.

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
- [ ] Production Docker Compose
- [ ] Health check endpoint
- [ ] E2E test senaryosu
- [ ] README.md ve API dokumantasyonu
