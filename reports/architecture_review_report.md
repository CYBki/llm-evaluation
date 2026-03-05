# RAG Evaluation System — Mimari İnceleme Raporu

**Tarih:** 4-5 Mart 2026  
**Kapsam:** 14 maddelik mimari inceleme, sorun tespiti ve çözüm uygulaması  
**Sistem:** Multi-agent RAG Evaluation API (FastAPI + PostgreSQL + Celery + Redis)  
**Sunucu:** 45.145.22.201:8000

---

## Özet

RAG evaluation sisteminin mimari incelemesi kapsamında 14 kritik sorun tespit edilmiş ve tamamı çözümlenmiştir. Sorunlar; metrik doğruluğu, performans, güvenlik, hata dayanıklılığı ve kod tutarlılığı kategorilerinde gruplandırılmıştır.

| Kategori | Madde Sayısı |
|---|---|
| Metrik Doğruluğu & Tutarlılık | 7 (Madde 1, 5, 6, 7, 12, 13, 14) |
| Performans & Altyapı | 3 (Madde 2, 3, 4) |
| Hata Dayanıklılığı | 2 (Madde 8, 9) |
| Güvenlik | 1 (Madde 10) |
| Kaynak Yönetimi | 1 (Madde 11) |

---

## Madde 1 — Faithfulness Metriği Eksikliği

### Problem
Sistemde `hallucination_score` metriki mevcut olmasına rağmen, RAG değerlendirmelerinde standart kabul edilen **faithfulness** metriği bulunmuyordu. Hallucination score ağırlıklı ceza sistemi kullanırken (contradiction > unsupported), faithfulness binary bazlı bir ölçüm sağlar ve farklı bir bakış açısı sunar.

### Çözüm
Mevcut hallucination claim analizi üzerine inşa edilen faithfulness metriği eklendi. Ekstra LLM çağrısı gerektirmeden, aynı claim listesinden `faithful_count / total` oranı hesaplanır.

### Değişiklikler
- **app/evaluation/rag_metrics.py** — `compute_hallucination_rubric` fonksiyonuna faithfulness hesaplaması eklendi
- **app/evaluation/evaluator.py** — `_OVERALL_WEIGHTS` sözlüğüne faithfulness (0.10 ağırlık) eklendi
- **app/schemas/ingest.py** — `ScoresResponse` ve `VerdictsResponse` şemalarına faithfulness alanı eklendi
- **app/routers/traces.py** — Response builder fonksiyonlarına faithfulness eklendi
- **app/models/evaluation.py** — `StepEvaluationResult` modeline faithfulness ve faithfulness_claims kolonları eklendi
- **app/metrics/definitions.py** — Faithfulness metrik tanımı ve eşik değerleri eklendi
- **alembic/versions/0007_add_faithfulness_to_steps.py** — Veritabanı migration dosyası oluşturuldu

---

## Madde 2 — HTTP Connection Pooling Eksikliği

### Problem
`llm_client.py`'de her LLM çağrısı için yeni bir `httpx.AsyncClient` oluşturuluyordu. Her çağrıda TCP bağlantısı açılıp TLS handshake yapılıyordu. Tek bir trace evaluation'ında 5-8 LLM çağrısı yapıldığı düşünülürse, çağrı başına ~500ms-1s ek gecikme oluşuyordu.

### Çözüm
Class-level paylaşımlı `httpx.AsyncClient` ile connection pooling uygulandı. Tüm LLM çağrıları aynı TCP/TLS bağlantılarını yeniden kullanır.

### Değişiklikler
- **app/evaluation/llm_client.py** — `_shared_http_client` class attribute'u, `_get_http_client()` classmethod'u (lazy init, max_connections=20, keepalive=10, http2=True), `close_shared_client()` graceful shutdown metodu eklendi
- **app/main.py** — `lifespan` context manager eklendi; uygulama kapanırken paylaşımlı HTTP client düzgün şekilde kapatılır

### Performans Etkisi
- Çağrı başına TLS handshake overhead: **~500ms → ~5ms** (mevcut bağlantı yeniden kullanımı)
- Trace başına toplam tasarruf: **~2-5 saniye**

---

## Madde 3 — asyncio.new_event_loop() Anti-Pattern

### Problem
`evaluation_service.py`'de her evaluation için `asyncio.new_event_loop()` ile yeni event loop oluşturuluyordu. Bu Python'da bilinen bir anti-pattern'dir ve kaynak sızıntısına, thread güvensizliğine ve performans düşüşüne yol açar. Ayrıca step evaluation'ları sıralı çalışıyordu (paralel değil).

### Çözüm
`asyncio.run()` ile standart event loop kullanımına geçildi. Step evaluation'ları `asyncio.gather()` ile paralel çalıştırılır.

### Değişiklikler
- **app/services/evaluation_service.py** — `evaluate_trace_and_persist()` fonksiyonu refactor edildi; `asyncio.run(_evaluate_trace_async())` kullanılır, step evaluation'ları `asyncio.gather(*step_coros, return_exceptions=True)` ile paralelize edildi

### Performans Etkisi
- 5 step'li bir trace: **sıralı ~25s → paralel ~8s** (step'ler eşzamanlı çalışır)

---

## Madde 4 — Prompt Token Limitlerinin Olmaması

### Problem
LLM prompt builder fonksiyonlarında hiçbir girdi uzunluk kontrolü yoktu. Çok uzun context'ler veya cevaplar doğrudan prompt'a ekleniyordu. Bu, OpenAI context window sınırını aşarak hatalara veya beklenmedik truncation'a yol açabilirdi.

### Çözüm
Tüm prompt builder fonksiyonlarına yapılandırılabilir truncation limitleri eklendi. Limitler aşıldığında `...[truncated]` eki ile kesilir ve log yazılır.

### Değişiklikler
- **app/evaluation/prompt_utils.py** — Yeni dosya: `truncate_text()` ve `truncate_contexts()` fonksiyonları
- **app/config.py** — Yapılandırılabilir limitler eklendi: `max_question_chars=8000`, `max_answer_chars=40000`, `max_context_total_chars=80000`, `max_single_context_chars=20000`, `max_ground_truth_chars=10000`
- **app/evaluation/prompts.py** — Tüm 8 `build_*_user_prompt` fonksiyonuna truncation uygulandı

---

## Madde 5 — Completeness Metriğinde Tutarsızlık

### Problem
Completeness metriğinde LLM'den "key point çıkar" deniliyordu ancak kaç key point çıkarılacağı belirlenmemişti. Aynı soru için bir çalışmada 3, diğerinde 7 key point çıkarılabilirdi. Bu, `covered / total` oranını nondeterministik yapıyordu.

### Çözüm
Key point sayısı, sorunun kelime sayısına göre deterministik hale getirildi:
- ≤15 kelime → 3 key point
- ≤40 kelime → 4 key point
- >40 kelime → 5 key point

### Değişiklikler
- **app/evaluation/prompts.py** — `_key_point_count(question)` fonksiyonu eklendi; `build_completeness_user_prompt` fonksiyonunda LLM'e "Extract exactly N key points" talimatı verilir

---

## Madde 6 — Gereksiz Specificity Metriğinin Kaldırılması

### Problem
Specificity (özgüllük) metriği, `answer_relevancy` ve `completeness` metrikleri ile yüksek korelasyona sahipti. Bir cevap specific ise zaten relevant ve complete olma olasılığı yüksektir. Bu, aynı sinyalin çift sayılmasına neden oluyordu.

### Çözüm
Specificity metriği sistemden tamamen kaldırıldı. Ağırlığı diğer metriklere dağıtıldı.

### Değişiklikler
- **app/evaluation/prompts.py** — RUBRIC_BLOCK'tan SPECIFICITY bölümü, STAGE_2_JSON_SCHEMA'dan specificity alanı ve _EXAMPLE_JSON'dan specificity kaldırıldı
- **app/evaluation/evaluator.py** — `_FLOAT_FIELDS`, return dict'leri ve regex fallback'ten specificity kaldırıldı
- **app/schemas/ingest.py** — `EvaluationDetailResponse`'dan specificity kaldırıldı
- **app/routers/traces.py** — Detail response builder'lardan specificity kaldırıldı
- **app/services/evaluation_service.py** — DB persist mantığından specificity kaldırıldı
- **app/main.py** — API açıklamasından specificity kaldırıldı, faithfulness eklendi

---

## Madde 7 — Metrik Ağırlıklarının Dengesizliği

### Problem
Specificity kaldırıldıktan ve faithfulness eklendikten sonra ağırlıkların yeniden dengelenmesi gerekiyordu. Özellikle:
- `hallucination_score` (0.15) ve `faithfulness` (0.15) aynı claim listesinden hesaplanıyordu — toplam 0.30 doğruluk payı çift sayma etkisi yaratıyordu
- `answer_relevancy` (0.10) çok düşüktü
- `helpfulness` (0.10) bağımsız bir sinyal olmasına rağmen yeterince ağırlık almıyordu

### Çözüm
İki opsiyon analiz edildi (senaryolarla sayısal karşılaştırma yapıldı). Opsiyon B seçildi: faithfulness 0.10'a düşürüldü, helpfulness 0.15'e çıkarıldı. Doğruluk payı 0.30→0.25'e düştü, metrik çeşitliliği artırıldı.

### Son Ağırlık Tablosu

| Metrik | Ağırlık | Kaynak |
|---|---|---|
| hallucination_score | 0.15 | RAG (claim analizi) |
| faithfulness | 0.10 | RAG (claim analizi) |
| answer_relevancy | 0.15 | RAG (embedding similarity) |
| completeness | 0.10 | RAG (key-point coverage) |
| context_precision | 0.10 | RAG (analitik) |
| context_recall | 0.10 | RAG (analitik) |
| helpfulness | 0.15 | Stage 1/2 (LLM yargısı) |
| coherence | 0.05 | Stage 1/2 (LLM yargısı) |
| clarity | 0.05 | Stage 1/2 (LLM yargısı) |
| citation_check | 0.05 | RAG (regex + analitik) |
| **Toplam** | **1.00** | |

### Değişiklikler
- **app/evaluation/evaluator.py** — `_OVERALL_WEIGHTS` güncellendi

---

## Madde 8 — LLM Client'ta Retry Mekanizması Eksikliği

### Problem
`llm_client.py`'de hiçbir HTTP seviyesinde retry yoktu. OpenAI 429 (rate limit), 503 (overloaded) veya timeout döndüğünde istek direkt başarısız oluyordu. Bu geçici hatalar normalde birkaç saniye sonra düzelir, ama sistem her seferinde tüm evaluation'ı kaybediyordu.

### Çözüm
`_request_with_retry` metodu eklendi. Tüm HTTP çağrıları (chat_completion + create_embeddings) bu metottan geçer.

### Özellikler
- **3 deneme** (1 orijinal + 2 retry)
- **Exponential backoff:** 1s → 2s
- **Retry-After header desteği** (429 yanıtlarında)
- **Retryable hatalar:** 429, 500, 502, 503, 529 + timeout + HTTP hataları
- **Non-retryable hatalar:** 400, 401, 403, 404 → direkt fail
- Her retry denemesinde warning log

### Değişiklikler
- **app/evaluation/llm_client.py** — `_request_with_retry` metodu eklendi; `chat_completion` ve `create_embeddings` metodları bu metodu kullanacak şekilde güncellendi

---

## Madde 9 — Circuit Breaker Pattern Eksikliği

### Problem
Retry mekanizması tek bir istek için iyi çalışır. Ancak OpenAI tamamen down olduğunda her trace evaluation'ı 3 deneme × 120s timeout = ~360s bekler. Ardışık gelen tüm istekler aynı kaderi yaşar. Worker thread'leri kilitlenir, kuyruk şişer, DB bağlantı havuzu tükenir.

### Çözüm
Elektrik sigortası benzeri circuit breaker pattern uygulandı:

```
CLOSED (normal) ──[5 ardışık hata]──→ OPEN (devre kesildi, 0ms yanıt)
                                        │
                                   [30s sonra]
                                        ▼
                                   HALF_OPEN (tek deneme)
                                   ┌────┴────┐
                              [başarılı]  [başarısız]
                                   │         │
                                CLOSED     OPEN
```

### Özellikler
- **Eşik:** 5 ardışık hata → OPEN
- **Recovery timeout:** 30 saniye
- **OPEN durumda:** HTTP çağrısı yapılmaz, anında `LLMClientError` fırlatılır (0ms bekleme)
- **HALF_OPEN:** Tek probe isteği; başarılıysa CLOSED'a döner
- **Non-retryable hatalar** (400, 401, 403, 404) circuit breaker'ı tetiklemez
- Class-level: tüm LLM çağrıları aynı circuit breaker'ı paylaşır

### Değişiklikler
- **app/evaluation/llm_client.py** — `_CBState` enum, `_CircuitBreaker` sınıfı eklendi; `_request_with_retry` metodu circuit breaker ile entegre edildi; `OpenAILLMClient._circuit_breaker` class-level attribute olarak tanımlandı

---

## Madde 10 — CORS allow_origins=["*"] Güvenlik Açığı

### Problem
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Tüm domainlere izin
    allow_credentials=True,       # Cookie/auth header otomatik gönderilir
)
```

Bu kombinasyon CSRF saldırılarına açıktır. Kötü niyetli bir site, giriş yapmış kullanıcının kimlik bilgileriyle API'yi çağırabilir. Ayrıca `*` ile `allow_credentials=True` bazı tarayıcılarda güvenlik kısıtlaması nedeniyle çalışmaz.

### Çözüm
CORS yapılandırması `.env` dosyasından okunur hale getirildi. Varsayılan olarak CORS middleware eklenmez (en güvenli).

### Kullanım
```env
# Production: sadece belirli originler
CORS_ORIGINS=https://app.example.com,https://admin.example.com

# Development: tüm originler (credentials olmadan)
CORS_ORIGINS=*

# Varsayılan (boş): CORS middleware eklenmez
CORS_ORIGINS=
```

### Değişiklikler
- **app/config.py** — `cors_origins: str = ""` ayarı eklendi
- **app/main.py** — Hardcoded `["*"]` yerine `settings.cors_origins`'den okuyan koşullu middleware konfigürasyonu; `allow_credentials` `*` kullanıldığında otomatik `False` yapılır

---

## Madde 11 — Health Endpoint'te DB Session Leak Riski

### Problem
```python
def health():
    db = SessionLocal()           # Session açıldı
    db.execute(text("SELECT 1"))  # BURDA EXCEPTION OLURSA?
    db.close()                    # Bu satır ATLANIR → session açık kalır
```

`db.execute()` exception fırlatırsa (DB bağlantı kopması, timeout), akış `except` bloğuna gider ve `db.close()` hiç çağrılmaz. Session havuza geri dönmez, bağlantılar tükenir.

### Çözüm
`with` context manager kullanıldı. Python'un `try/finally` sarmalayıcısıdır — ne olursa olsun (exception, return) bloktan çıkınca `__exit__` çağrılır ve session kapatılır.

```python
def health():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    # __exit__ otomatik çağrılır → db.close() garanti
```

### Değişiklikler
- **app/main.py** — Health endpoint'te `SessionLocal()` context manager olarak kullanıldı

---

## Madde 12 — Stage 1 Prompt'ta Context Numaralama Eksikliği

### Problem
Stage 1 prompt'unda context'ler numarasız listeleme ile sunuluyordu:
```
- İstanbul'un nüfusu 16 milyondur.
- Ankara başkenttir.
```

Oysa RAG metric prompt'ları (hallucination, citation, context_precision) numaralı format kullanıyordu:
```
[0] İstanbul'un nüfusu 16 milyondur.
[1] Ankara başkenttir.
```

Bu tutarsızlık nedeniyle Stage 1 reasoning'de LLM hangi context'e atıfta bulunduğunu belirtemiyordu. Stage 2 parse ve diğer metriklerle uyumsuzluk oluşuyordu.

### Çözüm
Stage 1 prompt'u da aynı `[i]` numaralama formatına geçirildi.

### Değişiklikler
- **app/evaluation/prompts.py** — `build_stage_1_user_prompt` fonksiyonundaki `f"- {item}"` formatı `f"[{i}] {c}"` enumerate formatına değiştirildi

---

## Madde 13 — Hallucination Detection'da Agreement Claim'lerinin Score'u Etkilemesi

### Problem
```python
total = len(claims)  # agreement + unsupported + contradiction HEPSİ
h_score = 1 - (weighted_penalty / total)
```

Aynı gerçeklik (1 unsupported claim) için LLM'in kaç agreement claim çıkardığına göre score değişiyordu:
- 9 agreement + 1 unsupported = `1 - 0.6/10 = 0.94`
- 3 agreement + 1 unsupported = `1 - 0.6/4 = 0.85`

Agreement claim sayısı nondeterministik olduğundan, aynı cevap farklı skorlar alabiliyordu.

### Çözüm
**Capped penalty** yaklaşımına geçildi. Her problematic claim sabit bir miktar düşürür, agreement claim'leri formüle hiç girmez:
- **Unsupported claim:** -0.15 (eski: -0.6/total)
- **Confirmed contradiction:** -0.30 (eski: -1.0/total)
- **Faithfulness:** her unfaithful claim -0.20

Artık kaç agreement claim olursa olsun 1 unsupported → her zaman 0.85.

### Değişiklikler
- **app/evaluation/rag_metrics.py** — Penalty sabitleri güncellendi (`_HALLUCINATION_UNSUPPORTED_PENALTY=0.15`, `_HALLUCINATION_CONTRADICTION_PENALTY=0.30`, `_FAITHFULNESS_PER_CLAIM_PENALTY=0.20`); `total`'e bölen formül yerine `max(0, 1 - total_penalty)` capped penalty formülüne geçildi

---

## Madde 14 — Completeness'ın Hem Stage 1 Hem RAG Pipeline'da Hesaplanması

### Problem
```python
"completeness": rag_results.get("completeness") or parsed.get("completeness")
```

Completeness iki farklı yerde, iki farklı metodoloji ile hesaplanıyordu:
1. **Stage 1 (rubric-based):** LLM'in subjektif 0-1 yargısı
2. **RAG pipeline (key-point based):** Analitik key point coverage oranı

`or` operatörü iki sorun yaratıyordu:
- RAG completeness gerçekten **0.0** ise (hiçbir key point kapsanmamış), Python `0.0`'ı falsy sayıp Stage 1'e fallback ediyordu → yanlış yüksek skor
- İki farklı ölçek (analitik vs subjektif) karışıyordu → tutarsız davranış

### Çözüm
Stage 1 fallback tamamen kaldırıldı. Completeness sadece RAG key-point pipeline'dan gelir. `None` ise dynamic normalization atlar (ağırlık diğer metriklere dağıtılır). `0.0` ise gerçek skor olarak kabul edilir.

### Değişiklikler
- **app/evaluation/evaluator.py** — `_compute_overall_score` ve ana return dict'teki `rag_results.get("completeness") or parsed.get("completeness")` → `rag_results.get("completeness")` olarak değiştirildi (2 yer)

---

## Etkilenen Dosya Özeti

| Dosya | Etkilenen Maddeler |
|---|---|
| app/evaluation/llm_client.py | 2, 8, 9 |
| app/evaluation/evaluator.py | 1, 6, 7, 14 |
| app/evaluation/prompts.py | 4, 5, 6, 12 |
| app/evaluation/rag_metrics.py | 1, 13 |
| app/evaluation/prompt_utils.py | 4 (yeni dosya) |
| app/services/evaluation_service.py | 3, 6 |
| app/config.py | 4, 10 |
| app/main.py | 2, 6, 10, 11 |
| app/schemas/ingest.py | 1, 6 |
| app/routers/traces.py | 1, 6 |
| app/models/evaluation.py | 1 |
| app/metrics/definitions.py | 1 |
| alembic/versions/0007_*.py | 1 (yeni dosya) |
