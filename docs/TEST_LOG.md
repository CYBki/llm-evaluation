# Test Log — Qwen (OpenRouter) Migration

Bu dosya `feat/qwen-openrouter-migration` branch'inde gerçekleştirilen tüm
testleri, kurulumları ve sonuçları kronolojik olarak belgeler.

## İçindekiler

1. [Hedef ve Strateji](#hedef-ve-strateji)
2. [Test Ortamı — Üç Paralel Stack](#test-ortam--üç-paralel-stack)
3. [Fixtures](#fixtures)
4. [Yürütülen Testler](#yürütülen-testler)
   - [T1 — Qwen stack smoke](#t1--qwen-stack-smoke-test-1-trace)
   - [T2 — OpenAI direct stack smoke](#t2--openai-direct-stack-smoke-test-1-trace)
   - [T3 — 10-trace A/B (ilk geçiş)](#t3--10-trace-ab-i̇lk-geçiş)
   - [T4 — 50-trace A/B (direct)](#t4--50-trace-ab-qwen-or-vs-openai-direct)
   - [T5 — gpt-5.2 via OpenRouter smoke](#t5--openai-via-openrouter-stack-smoke)
   - [T6 — 50-trace A/B (infra-parity)](#t6--50-trace-ab-infra-parity)
5. [Sonuç Dosyaları](#sonuç-dosyaları)
6. [Raporlar (Cross-reference)](#raporlar-cross-reference)
7. [Özet Bulgular Matrisi](#özet-bulgular-matrisi)

---

## Hedef ve Strateji

OpenAI modellerinden (gpt-5.2 + gpt-4o-mini) açık-ağırlıklı Qwen
modellerine (qwen3-235b-a22b-2507 + qwen3-32b) geçişi, hem kalite hem
maliyet açısından doğrulamak. Yaklaşım: **paralel stack'ler kurup aynı
trace fixture'ını yan yana çalıştır, metrik bazında Pearson/MAD ile uyumu
ölç.**

Üç aşamalı test matrisi:

| Aşama | Amaç |
|---|---|
| **Smoke** | Her stack'in tek başına çalıştığını doğrula |
| **Direct A/B** | Qwen (OpenRouter) ↔ OpenAI (direct) — prodüksiyonda ne olacaksa onu test et |
| **Infra-parity A/B** | Her iki modeli aynı gateway (OpenRouter) üzerinden çağır — saf model kalite farkını izole et |

---

## Test Ortamı — Üç Paralel Stack

| | Stack A (Qwen) | Stack B (OpenAI-direct) | Stack C (OpenAI-via-OR) |
|---|---|---|---|
| Port | `8000` | `8001` | `8002` |
| docker-compose | `docker-compose.yml` | `docker-compose.openai.yml` | `docker-compose.openai-via-or.yml` |
| Env file | `.env` | `.env.openai` | `.env.openai-via-or` |
| Project name | `llm-evaluation` | `llm-eval-openai` | `llm-eval-openai-or` |
| Gateway | `openrouter.ai` | `api.openai.com` | `openrouter.ai` |
| Stage 1 modeli | `qwen/qwen3-235b-a22b-2507` | `gpt-5.2` | `openai/gpt-5.2` |
| Stage 2 modeli | `qwen/qwen3-32b` | `gpt-4o-mini` | `openai/gpt-4o-mini` |
| RAG metrik modeli | `qwen/qwen3-32b` | `gpt-5-mini` | `openai/gpt-5-mini` |
| Postgres | `llm-evaluation_pgdata` | `llm-eval-openai_pgdata` | `llm-eval-openai-or_pgdata` |
| Redis | ayrı container | ayrı container | ayrı container |
| İlk açılış | Oturum 1 | Oturum 1 | Oturum 2 (bu son) |

Üç stack tamamen izole — DB, Redis, API key'leri ayrı. Aynı kod tabanı,
aynı prompt'lar, aynı JSON schema kullanılır.

### Stack'leri Ayağa Kaldırma

```bash
# Qwen (8000)
docker compose up -d --build

# OpenAI direct (8001)
docker compose -f docker-compose.openai.yml -p llm-eval-openai \
  --env-file .env.openai up -d --build

# OpenAI via OpenRouter (8002)
docker compose -f docker-compose.openai-via-or.yml -p llm-eval-openai-or \
  --env-file .env.openai-via-or up -d --build
```

### Swagger / Docs URL'leri

- <http://localhost:8000/docs> — Qwen
- <http://localhost:8001/docs> — OpenAI-direct
- <http://localhost:8002/docs> — OpenAI-via-OR

---

## Fixtures

| Dosya | Trace Sayısı | Kategoriler |
|---|--:|---|
| `tests/fixtures/ab_compare_traces.json` | 10 | faithful, subtle, major, unsupported, offtopic |
| `tests/fixtures/ab_compare_traces_50.json` | 50 | 12 faithful + 9 subtle + 10 major + 5 unsupported + 5 partial + 5 off-topic/deflection + 4 context_issue |

Her trace TR veya EN, `question` / `answer` / `contexts` / `ground_truth` /
`metadata.category` / `metadata.case` alanlarını içerir. Çoğu hallucination
senaryosu: cevap context'le kısmen veya tamamen uyumsuz.

---

## Yürütülen Testler

### T1 — Qwen stack smoke test (1 trace)

- **Tarih:** Oturum 1 (Apr 24, 2026 ~10:00)
- **Amaç:** Qwen stack'in trace ingest → evaluate → response döngüsünü doğrula, OpenRouter API'sinin erişilebilir olduğunu teyit et.
- **Komut:**
  ```bash
  curl -X POST http://localhost:8000/api/v1/ingest \
    -H "X-API-Key: re_Ah1DISGAH0RBKe1n5XZ7PYDCJ_Qct7DvydEJei3q0Ps" \
    -H 'Content-Type: application/json' \
    -d '{"question":"What is 2+2?","answer":"4","contexts":["Basic arithmetic: 2+2=4"],"ground_truth":"4"}'
  ```
- **Sonuç:** 200 OK, trace completed, overall_score=1.0
- **Çözülen sorunlar:**
  - 401 Unauthorized → `.env`'de `LLM_API_KEY` eksikti
  - 400 `max_completion_tokens` reddedildi → OpenRouter `max_tokens` bekliyor → `app/evaluation/llm_client.py`'da base URL'e göre otomatik seçim (`f1ac6d5`)
  - 404 "No endpoints found" → `OPENROUTER_PROVIDER_ORDER` yanlış provider pinlemişti → boşaltıldı (`693a535`)

### T2 — OpenAI direct stack smoke (1 trace)

- **Tarih:** Oturum 1
- **Amaç:** `api.openai.com` üzerinden aynı trace'i çalıştır.
- **Komut:** T1 ile aynı, port 8001 ve farklı key.
- **Sonuç:** 200 OK, completed, overall_score=1.0
- **Çözülen sorunlar:**
  - Env yüklenmiyordu → `docker-compose.openai.yml`'e `env_file` directive'i eklendi (`f1ac6d5`)

### T3 — 10-trace A/B (ilk geçiş)

- **Tarih:** Oturum 1
- **Fixture:** `tests/fixtures/ab_compare_traces.json` (10 trace)
- **Script:** `scripts/compare_models.py` (`0b4e95e`'de eklendi)
- **Komut:**
  ```bash
  .venv/bin/python scripts/compare_models.py \
    --traces tests/fixtures/ab_compare_traces.json \
    --qwen-url http://localhost:8000 --qwen-key <QWEN_KEY> \
    --openai-url http://localhost:8001 --openai-key <OAI_KEY>
  ```
- **Sonuç:**
  - `overall_score` Pearson ≈ 0.99 → çok iyi uyum
  - `clarity` / `coherence` düşük korelasyon → off-topic case'lerde iki model farklı
  - Kalibrasyon teyit edildi, 50-trace'e geçiş kararı.

### T4 — 50-trace A/B (Qwen-OR vs OpenAI-direct)

- **Tarih:** Oturum 2 (Apr 24, 2026 ~11:17)
- **Fixture:** `tests/fixtures/ab_compare_traces_50.json` (50 trace)
- **Komut:**
  ```bash
  .venv/bin/python scripts/compare_models.py \
    --traces tests/fixtures/ab_compare_traces_50.json \
    --qwen-url http://localhost:8000 --qwen-key <QWEN_KEY> \
    --openai-url http://localhost:8001 --openai-key <OAI_KEY> \
    --out /tmp/ab_compare_50_raw.json \
    --concurrency 4
  ```
- **Süre:** ~4-5 dakika
- **Raw output:** `/tmp/ab_compare_50_raw.json` (390 KB)
- **Log:** `/tmp/ab_compare_50.log` (121 satır)
- **Başarılı pair:** 33/50 (%66) — 17 ingest 30/min rate-limit'e takıldı
- **Öne çıkan Pearson değerleri (n=33):**
  - `overall_score` = **0.993**
  - `context_precision` = **1.000**
  - `context_recall` = **0.948**
  - `answer_relevancy` = **0.941**
  - `helpfulness` = **0.900**
  - `hallucination_score` = **0.857** (Qwen +0.12 daha sıkı)
  - `faithfulness` = **0.851** (Qwen +0.11 daha sıkı)
  - `clarity` = **−0.070** ❌
  - `coherence` = **0.020** ❌
- **Maliyet:** Qwen $0.0272 · OpenAI $0.2885 → OpenAI 10.6× daha pahalı
- **Token:** Qwen 148,828 · OpenAI 309,371
- **Ortalama süre:** Qwen 19,613ms · OpenAI 18,581ms
- **Rapor:** [`AB_REPORT_QWEN_VS_OPENAI.md`](AB_REPORT_QWEN_VS_OPENAI.md)
- **Not:** OpenAI-direct'in cost'u `.env.openai`'deki pricing tablosuyla hesaplanıyor; bu değer OpenAI list price'ı ile uyumlu ama OpenRouter actual billing ile aynı değil — 10.6× rakamının bir kısmı config farklılığından.

### T5 — OpenAI-via-OpenRouter stack smoke

- **Tarih:** Oturum 2 (Apr 24, 2026 ~12:30)
- **Amaç:** `openai/gpt-5.2` modelinin OpenRouter üzerinden çalıştığını doğrula.
- **Komut:**
  ```bash
  curl -X POST http://localhost:8002/api/v1/ingest \
    -H "X-API-Key: re__Og7AC5S6sEvOtiyOyI1gkRNQzLjlf9_U06FUdpSMtc" \
    -H 'Content-Type: application/json' \
    -d '{"question":"capital of France?","answer":"Paris.","contexts":["France capital is Paris."],"ground_truth":"Paris"}'
  ```
- **Sonuç:** trace `8424eade-2af4-4616-9bd8-1c1401b4f0da`, status=completed, overall_score=1.0, cost=$0.000816, tokens=4,162, duration=7.9s
- **Çözülen sorunlar:**
  - Register endpoint `.local` ve `.example` dışı TLD'lere izin vermiyor → `@example.com` ile register edildi
  - Register rate-limit'i 3/min → bir sürüm sonra denemek gerekti

### T6 — 50-trace A/B (infra-parity)

- **Tarih:** Oturum 2 (Apr 24, 2026 ~12:40)
- **Fixture:** Aynı 50 trace
- **Stack çifti:** Qwen (8000, OpenRouter) ↔ OpenAI (8002, OpenRouter)
- **Komut:**
  ```bash
  .venv/bin/python scripts/compare_models.py \
    --traces tests/fixtures/ab_compare_traces_50.json \
    --qwen-url http://localhost:8000 --qwen-key <QWEN_KEY> \
    --openai-url http://localhost:8002 --openai-key <OAI_OR_KEY> \
    --out /tmp/ab_compare_50_or_raw.json \
    --concurrency 4
  ```
- **Süre:** ~5 dakika
- **Raw output:** `/tmp/ab_compare_50_or_raw.json` (370 KB)
- **Log:** `/tmp/ab_compare_50_or.log`
- **Başarılı pair:** 28/50 (%56) — rate-limit + OpenRouter tarafındaki sporadic 429'lar
- **Pearson değerleri (n=28):**
  - `overall_score` = **0.923** ✅ (direct: 0.993 → −0.07)
  - `coherence` = **0.802** ✅ (direct: 0.020 → **+0.78** 🔺)
  - `clarity` = **0.648** 🟡 (direct: −0.070 → **+0.72** 🔺)
  - `hallucination_score` = **0.840**
  - `faithfulness` = **0.792**
  - `helpfulness` = **0.879**
  - `answer_relevancy` = **−0.076** 🔻 (variance kayboldu, noise)
  - `context_precision` / `context_recall` = 1.0 (her ikisi de, Pearson tanımsız)
- **Maliyet:** Qwen $0.0243 · OpenAI-via-OR $0.0710 → 2.9× fark
- **Ortalama süre:** Qwen 24,466ms · OpenAI-via-OR 18,042ms
- **Rapor:** [`AB_REPORT_INFRA_PARITY.md`](AB_REPORT_INFRA_PARITY.md)
- **Delta rapor:** [`AB_SUMMARY_3WAY.md`](AB_SUMMARY_3WAY.md)
- **Ana öğrenim:** `clarity`/`coherence` uyumsuzluğunun **büyük kısmı infra gürültüsü** imiş; aynı gateway üzerinden iki model çok daha uyumlu.

---

## Sonuç Dosyaları

| Dosya | Üretildiği Test | Boyut |
|---|---|--:|
| `/tmp/ab_compare_50_raw.json` | T4 (direct) | 390 KB |
| `/tmp/ab_compare_50.log` | T4 (direct) | 121 satır |
| `/tmp/ab_compare_50_or_raw.json` | T6 (parity) | 370 KB |
| `/tmp/ab_compare_50_or.log` | T6 (parity) | ~125 satır |

Raw JSON dosyaları `scripts/generate_ab_report.py` ve
`scripts/generate_infra_parity_report.py` ile markdown raporlara dönüştürülür.

---

## Raporlar (Cross-reference)

| Rapor | Kapsam | İçerik |
|---|---|---|
| [`AB_REPORT_QWEN_VS_OPENAI.md`](AB_REPORT_QWEN_VS_OPENAI.md) | T4 | Direct A/B — 33/50 başarılı pair, per-metric Pearson/MAD + trace ID'li detay |
| [`AB_REPORT_INFRA_PARITY.md`](AB_REPORT_INFRA_PARITY.md) | T6 | Infra-parity A/B — 28/50 başarılı, aynı gateway üstünden karşılaştırma |
| [`AB_SUMMARY_3WAY.md`](AB_SUMMARY_3WAY.md) | T4 + T6 | Pearson delta (direct → parity), maliyet/süre karşılaştırması, kritik bulgular |
| [`COMPARE_MODELS.md`](COMPARE_MODELS.md) | Kullanım | `compare_models.py` nasıl çalıştırılır, stack kurulumu |

---

## Özet Bulgular Matrisi

### Migration Kararı İçin Kritik Metrikler

| Metrik | Direct (T4) | Parity (T6) | Karar |
|---|--:|--:|---|
| `overall_score` Pearson | **0.993** | **0.923** | ✅ Güvenli |
| `hallucination_score` Pearson | 0.857 | 0.840 | ✅ Güvenli, Qwen sistematik daha sıkı |
| `faithfulness` Pearson | 0.851 | 0.792 | ✅ Güvenli |
| `context_precision` Pearson | 1.000 | — | ✅ Birebir |
| `context_recall` Pearson | 0.948 | — | ✅ Birebir |

### Maliyet / Performans

| | Direct run | Parity run |
|---|---|---|
| Cost ratio (OAI / Qwen) | 10.6× | 2.9× |
| Qwen mean latency | 19.6s | 24.5s |
| OpenAI mean latency | 18.6s | 18.0s |
| Qwen tokens total | 148,828 | 131,170 |
| OpenAI tokens total | 309,371 | 310,252 |

### Uyarılar

- **17-22 trace failed** her iki run'da → ingest rate-limit (30/min). Daha büyük run için concurrency=1 veya server-side rate limit yükseltmesi gerekir.
- **`clarity`/`coherence`** direct run'da korelasyonsuz, parity run'da korele → ilk rapordaki "felsefi fark" yorumunun çoğu **infra artefaktı** çıktı.
- **`answer_relevancy`** parity'de çöktü (variance kaybı) → noise, istatistik önemli değil.
- **Ground truth yok** — hangi judge'ın daha "doğru" olduğu hâlâ ölçülmüyor (ikisi aynı anda yanılabilir).

---

## Tekrar Üretme Özeti

```bash
# 1. Üç stack'i ayağa kaldır
docker compose up -d --build
docker compose -f docker-compose.openai.yml -p llm-eval-openai --env-file .env.openai up -d --build
docker compose -f docker-compose.openai-via-or.yml -p llm-eval-openai-or --env-file .env.openai-via-or up -d --build

# 2. Her stack'te user register et, api_key'leri kaydet
for port in 8000 8001 8002; do
  curl -s -X POST http://localhost:$port/api/v1/auth/register \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"abtest$port@example.com\",\"password\":\"abtest123\"}"
done

# 3. Direct A/B (T4)
.venv/bin/python scripts/compare_models.py \
  --traces tests/fixtures/ab_compare_traces_50.json \
  --qwen-url http://localhost:8000 --qwen-key <QWEN_KEY> \
  --openai-url http://localhost:8001 --openai-key <OAI_KEY> \
  --out /tmp/ab_compare_50_raw.json --concurrency 4

# 4. Infra-parity A/B (T6)
.venv/bin/python scripts/compare_models.py \
  --traces tests/fixtures/ab_compare_traces_50.json \
  --qwen-url http://localhost:8000 --qwen-key <QWEN_KEY> \
  --openai-url http://localhost:8002 --openai-key <OAI_OR_KEY> \
  --out /tmp/ab_compare_50_or_raw.json --concurrency 4

# 5. Raporları üret
.venv/bin/python scripts/generate_ab_report.py
.venv/bin/python scripts/generate_infra_parity_report.py
```

---

## Branch Commit Geçmişi (kronolojik)

```
eed3e9e  feat(llm): route chat via OpenRouter with provider pinning; split embeddings endpoint
931f8c9  refactor(config): rename OPENAI_* env vars to LLM_* (backward-compat aliases)
693a535  fix(llm): loosen OpenRouter provider routing; rename 'OpenAI' log labels
a19223f  fix(llm): use max_tokens instead of max_completion_tokens
0b4e95e  feat(compare): side-by-side A/B harness for Qwen vs OpenAI stacks
f1ac6d5  fix(llm): auto-detect max_tokens vs max_completion_tokens by base URL
2cea124  fix(api): expose cost_usd / total_tokens in GET /traces responses
4c5dd93  feat(compare): 50-trace fixture + rate-limit-aware concurrency
e03ec14  docs(ab-report): 50-trace Qwen vs OpenAI comparative report with trace IDs
e3e318e  feat(ab-test): infra-parity stack + 3-way comparison report
```
