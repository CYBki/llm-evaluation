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

Kullanicilar kendi RAG sistemlerine 2 satir SDK ekleyerek her soru-cevap etkilesiminin kalitesini otomatik olarak olcen bir SaaS evaluation platformu.

Kullanici herhangi bir dataset yuklemez. Gercek kullanimdaki her soru-cevap cifti SDK araciligiyla otomatik olarak yakalanir ve iki asamali (two-stage) LLM-as-Judge yontemiyle puanlanir.

Degerlendirme Mimarisi: Chain-of-Thought prompting ile ilk LLM serbest metin muhakeme uretir, ikinci LLM (veya ayni modelin ikinci cagrisi) bu muhakemeyi yapilandirilmis JSON skorlara donusturur. Bu sayede daha derin analiz, aciklanabilir puanlama ve claim bazli dogrulama saglanir.

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

Gun 3 - Carsamba - LLM Client ve Two-Stage Evaluation Engine

| Gorev |
|---|
| llm_client.py: OpenAI async wrapper, retry, hata yonetimi |
| Stage 1 prompt: Chain-of-Thought ile serbest metin muhakeme ureten prompt |
| Stage 2 prompt: Muhakeme metnini 8 metrik + reasoning + disagreement_claims JSON a donusturen prompt |
| evaluator.py: evaluate_trace() fonksiyonu (iki asamali cagri) |
| Ingest sonrasi otomatik evaluation, sonucu (skorlar + reasoning) DB ye kaydet |
| GET /api/v1/traces/{id} evaluation sonucu + reasoning_summary ile birlikte donsun |

Two-Stage Evaluation Akisi:
```
Asama 1: Question + Context + Answer → gpt-4o-mini → Serbest metin muhakeme
Asama 2: Muhakeme metni → gpt-4o-mini → Yapilandirilmis JSON (skorlar + reasoning + claims)
```

Beklenen cikti: Trace gonder, LLM iki asamada puanlasin, 8 metrik skoru + aciklama donsun.

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

Iki asamali LLM cagrisiyla tum metrikler puanlanir. Stage 1 serbest metin muhakeme uretir, Stage 2 yapilandirilmis JSON'a donusturur.

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

Ek Alanlar (Two-Stage ciktisi):

| Alan | Tip | Aciklama |
|---|---|---|
| reasoning_summary | string | Puanlamanin tek cumlelik gerekce ozeti |
| disagreement_claims | JSON array | Context-cevap uyumsuzluk analizi (claim bazli) |
| stage_1_reasoning | text | Stage 1 serbest metin muhakeme (ham cikti) |

### 4.3 Teslim Edilecekler

- [ ] FastAPI projesi + Docker Compose (API + PostgreSQL)
- [ ] User, Trace, EvaluationResult modelleri + migration
- [ ] POST /api/v1/auth/register
- [ ] Auth middleware (X-API-Key)
- [ ] POST /api/v1/ingest (tek trace + senkron eval)
- [ ] POST /api/v1/ingest/batch (toplu trace)
- [ ] GET /api/v1/traces (pagination)
- [ ] GET /api/v1/traces/{id} (detay + evaluation)
- [ ] Two-Stage LLM-as-Judge evaluator (Stage 1: CoT reasoning, Stage 2: JSON skorlama)
- [ ] reasoning_summary ve disagreement_claims ciktisi
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

Stage 1 (CoT Reasoning) serbest metin muhakeme uretir, Stage 2 yapilandirilmis JSON'a donusturur.

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
| answer_relevancy | FLOAT | NULLABLE | Soru-cevap benzerlik (Sprint 2) |
| faithfulness | FLOAT | NULLABLE | Contexte sadakat (Sprint 2) |
| hallucination | FLOAT | NULLABLE | Uydurma iddia orani (Sprint 2) |
| citation_check | FLOAT | NULLABLE | Citation dogrulama (Sprint 2) |
| reasoning_summary | TEXT | NULLABLE | Puanlamanin tek cumlelik gerekce ozeti |
| disagreement_claims | JSON | NULLABLE | Context-cevap uyumsuzluk analizi (claim bazli) |
| stage_1_reasoning | TEXT | NULLABLE | Stage 1 serbest metin muhakeme (ham CoT ciktisi) |
| raw_response | JSON | NULLABLE | Stage 2 LLM ham JSON yaniti |
| evaluated_at | TIMESTAMP | DEFAULT now() | Degerlendirme tarihi |
| model_used | VARCHAR(50) | NULLABLE | Kullanilan LLM modeli |

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
│   │   ├── prompts.py               # Stage 1 (CoT) ve Stage 2 (JSON) prompt sablonlari
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

### OpenAI API Maliyeti (gpt-4o-mini)

| Kalem | Birim Fiyat | Aciklama |
|---|---|---|
| Input tokens | $0.15 / 1M token | Prompt + soru + cevap + context |
| Output tokens | $0.60 / 1M token | JSON evaluation sonucu |

Iki asamali (two-stage) degerlendirme:
- Stage 1 Input: ~800 token (CoT prompt + soru + cevap + context)
- Stage 1 Output: ~400 token (serbest metin muhakeme)
- Stage 2 Input: ~600 token (Stage 2 prompt + muhakeme metni)
- Stage 2 Output: ~300 token (yapilandirilmis JSON + reasoning + claims)
- Toplam maliyet/trace: ~$0.00042

| Aylik Hacim | Trace/Ay | Tahmini Maliyet |
|---|---|---|
| Dusuk | 1,000 | ~$0.42 |
| Orta | 10,000 | ~$4.20 |
| Yuksek | 100,000 | ~$42.00 |
| Cok Yuksek | 1,000,000 | ~$420.00 |

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
- [ ] Stage 1 serbest metin muhakeme + Stage 2 yapilandirilmis JSON akisi calisiyor
- [ ] reasoning_summary ve disagreement_claims evaluation sonucunda donuyor
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
