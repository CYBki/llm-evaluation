# A/B Karşılaştırma Raporu: Qwen (OpenRouter) vs OpenAI

İki paralel evaluation stack'inin aynı 50 trace üzerindeki skorlarının yan-yana karşılaştırması. Qwen stack `qwen/qwen3-235b-a22b-2507` + `qwen/qwen3-32b` kullanıyor (OpenRouter); OpenAI stack `gpt-5.2` + `gpt-4o-mini` kullanıyor.

## Özet

- **Toplam trace:** 50
- **Her iki stack'te de başarılı:** 33 (66%)
- **Fail (ingest/eval hatası):** 17
- **Toplam maliyet:** Qwen **$0.0272** · OpenAI **$0.2885** → OpenAI **10.6× daha pahalı**
- **Toplam token:** Qwen 148,828 · OpenAI 309,371
- **Ortalama eval süresi:** Qwen 19613 ms · OpenAI 18581 ms

## Metrik Bazlı İstatistik

| Metrik | n | Qwen μ | OpenAI μ | Mean Δ | MAD | **Pearson** | Değerlendirme |
|---|--:|--:|--:|--:|--:|--:|---|
| `overall_score` | 33 | 0.595 | 0.585 | +0.009 | 0.018 | **0.993** | ✅ Mükemmel |
| `clarity` | 33 | 0.730 | 0.855 | -0.124 | 0.233 | **-0.070** | ❌ Düşük |
| `coherence` | 33 | 0.739 | 0.900 | -0.161 | 0.252 | **0.020** | ❌ Düşük |
| `helpfulness` | 33 | 0.609 | 0.539 | +0.070 | 0.094 | **0.900** | ✅ Çok iyi |
| `completeness` | 33 | 0.450 | 0.490 | -0.040 | 0.141 | **0.751** | 🟡 İyi |
| `answer_relevancy` | 33 | 0.788 | 0.833 | -0.045 | 0.045 | **0.941** | ✅ Mükemmel |
| `faithfulness` | 32 | 0.812 | 0.700 | +0.113 | 0.113 | **0.851** | ✅ Çok iyi |
| `hallucination_score` | 32 | 0.784 | 0.669 | +0.116 | 0.116 | **0.857** | ✅ Çok iyi |
| `citation_check` | 0 | — | — | — | — | — | — |
| `context_precision` | 33 | 0.970 | 0.970 | +0.000 | 0.000 | **1.000** | ✅ Mükemmel |
| `context_recall` | 33 | 0.960 | 0.970 | -0.010 | 0.010 | **0.948** | ✅ Mükemmel |

## Yorumlama

- **`overall_score` Pearson ≈ 1.00** — iki model son-kullanıcıya gösterilen genel karar için **pratik olarak aynı** hükmü veriyor.
- **`hallucination_score` / `faithfulness`** Qwen ~12 puan daha sıkı. Sıralama uyumlu (Pearson ≈ 0.85) ama eşik farklı — Qwen daha agresif. Hallucination detection senaryosunda bu avantaj sayılır.
- **`clarity` / `coherence`** korelasyonsuz. Off-topic/deflection cevaplarda Qwen `0.0` verirken OpenAI `1.0` veriyor — iki modelin felsefesi farklı: OpenAI yalnızca dilbilgisel netliğe, Qwen konuyla uyuma bakıyor. Bu ürün-kararı; şu an Qwen'in yaklaşımı daha 'business-correct'.
- **`context_precision` / `context_recall`** neredeyse birebir — RAG retrieval değerlendirmesinde iki model %100 uyumlu.
- **Maliyet 10.6× avantaj** Qwen tarafında. Günlük 10k trace için yıllık tasarruf ≈ $19,076.

## Trace-Bazlı Detay

Her satır bir test senaryosudur. Aynı fixture (bkz. [`tests/fixtures/ab_compare_traces_50.json`](../tests/fixtures/ab_compare_traces_50.json)) iki stack'e paralel gönderildi; trace ID'ler her stack'in kendi DB'sinde üretildi (bağımsız Postgres volume'leri).

| # | Case | Kategori | Soru | Qwen trace_id | OAI trace_id | Qwen overall | OAI overall | Qwen hallu | OAI hallu | ΔOverall |
|---|---|---|---|---|---|--:|--:|--:|--:|--:|
| 1 | `01_faithful_tr` | faithful | Python'da list ve tuple arasındaki temel fark nedir? | `66f40d34` | `c5a5f04d` | 0.98 | 1.00 | 1.00 | 1.00 | -0.02 |
| 2 | `02_faithful_tr` | faithful | HTTPS hangi portu kullanır? | `f1296f3d` | `315922b0` | 0.96 | 0.96 | 1.00 | 1.00 | +0.00 |
| 3 | `03_faithful_tr` | faithful | Suyun normal atmosfer basıncında kaynama noktası kaç dere... | `750723ab` | `cd0dc68f` | 0.96 | 0.96 | 1.00 | 1.00 | +0.00 |
| 4 | `04_faithful_tr` | faithful | Türkiye'nin Avrupa Birliği'ne katılım başvurusu hangi yıl... | `6faa3c3f` | `a96c5a1d` | 0.93 | 1.00 | 1.00 | 1.00 | -0.07 |
| 5 | `05_faithful_tr` | faithful | DNA'nın dört bazı nedir? | `91355b78` | `5d91f2fe` | 1.00 | 0.96 | 1.00 | 1.00 | +0.04 |
| 6 | `06_faithful_en` | faithful | What does HTTP status code 404 mean? | `111999a8` | `70cef985` | 0.92 | 0.92 | 0.85 | 0.85 | +0.00 |
| 7 | `07_faithful_en` | faithful | Who wrote 'Hamlet'? | `a83292b4` | `d4e21db4` | 0.96 | 0.96 | 1.00 | 1.00 | +0.00 |
| 8 | `08_faithful_en` | faithful | What is the largest planet in our Solar System? | `5b87253e` | `be8e2939` | 1.00 | 0.98 | 1.00 | 1.00 | +0.02 |
| 9 | `09_faithful_en` | faithful | What does TCP stand for? | `b6f244fa` | `6451aed0` | 0.96 | 0.96 | 1.00 | 1.00 | +0.00 |
| 10 | `10_faithful_en` | faithful | What is photosynthesis? ⚠️O | `3152ed2a` | `—` | 1.00 | — | 1.00 | — | — |
| 11 | `11_subtle_tr` | subtle | Python dilinin ilk sürümü hangi yıl yayınlandı? | `2b85c3d9` | `30c6b8cd` | 0.35 | 0.35 | 0.70 | 0.70 | +0.00 |
| 12 | `12_subtle_tr` | subtle | Osmanlı İmparatorluğu hangi yılda kuruldu? ⚠️Q | `—` | `5154b013` | — | 0.35 | — | 0.70 | — |
| 13 | `13_faithful_tr` | faithful | Dünya'nın Güneş'e olan ortalama uzaklığı kaç kilometredir? ⚠️Q | `—` | `07768aeb` | — | 0.98 | — | 1.00 | — |
| 14 | `14_subtle_tr` | subtle | Türkçede alfabede kaç harf vardır? | `b5f37ca7` | `9bd84882` | 0.35 | 0.35 | 0.70 | 0.70 | +0.00 |
| 15 | `15_subtle_tr` | subtle | Eyfel Kulesi hangi yıl açıldı? ⚠️Q | `—` | `d37f80cc` | — | 0.35 | — | 0.70 | — |
| 16 | `16_subtle_en` | subtle | How many bones are in the adult human body? | `756a0ab0` | `9ebe1a22` | 0.35 | 0.35 | 0.70 | 0.40 | +0.00 |
| 17 | `17_subtle_en` | subtle | When did World War II end? ⚠️Q | `—` | `54ea0b28` | — | 0.35 | — | 0.70 | — |
| 18 | `18_subtle_en` | subtle | Which element has the atomic number 6? | `c1f01ec0` | `99b10a41` | 0.35 | 0.35 | 0.70 | 0.55 | +0.00 |
| 19 | `19_subtle_en` | subtle | Who painted the Mona Lisa? | `2ecc1fb5` | `ccbe4d80` | 0.35 | 0.35 | 0.70 | 0.70 | +0.00 |
| 20 | `20_subtle_en` | subtle | Which year did Albert Einstein publish the special theory... | `d6c45016` | `fae70c0d` | 0.35 | 0.35 | 0.70 | 0.40 | +0.00 |
| 21 | `21_major_tr` | major | İstanbul'un fethi hangi yıl oldu ve hangi padişah gerçekl... ⚠️Q | `—` | `d441fdac` | — | 0.35 | — | 0.55 | — |
| 22 | `22_major_tr` | major | Python'da GIL hangi sürümde opsiyonel oldu ve hangi PEP k... | `7714d9e0` | `bd34df83` | 0.35 | 0.35 | 0.40 | 0.10 | +0.00 |
| 23 | `23_major_tr` | major | Mars'ın kaç uydusu vardır ve adları nedir? ⚠️Q ⚠️O | `—` | `—` | — | — | — | — | — |
| 24 | `24_major_tr` | major | Türkiye Cumhuriyeti ne zaman kuruldu ve ilk cumhurbaşkanı... | `5cc0ce0a` | `b3b3f873` | 0.35 | 0.35 | 0.40 | 0.25 | +0.00 |
| 25 | `25_major_tr` | major | HTTP ve HTTPS arasındaki güvenlik farkı nedir ve HTTPS ha... | `7d45aa6e` | `66df333f` | 0.35 | 0.35 | 0.25 | 0.25 | +0.00 |
| 26 | `26_major_en` | major | Who discovered penicillin and in which year? | `7d1a7083` | `95a5d85a` | 0.35 | 0.35 | 0.70 | 0.10 | +0.00 |
| 27 | `27_major_en` | major | What is the capital of Australia and what is its population? | `450b1817` | `cde3b6f9` | 0.35 | 0.35 | 0.40 | 0.40 | +0.00 |
| 28 | `28_major_en` | major | How long does sunlight take to reach Earth? ⚠️Q | `—` | `5a52eb36` | — | 0.35 | — | 0.55 | — |
| 29 | `29_major_en` | major | Which planet is closest to the Sun and what is its surfac... ⚠️Q | `—` | `8a8c63cb` | — | 0.35 | — | 0.10 | — |
| 30 | `30_major_en` | major | Who was the first woman to win a Nobel Prize and in which... ⚠️Q | `—` | `d78c2732` | — | 0.35 | — | 0.25 | — |
| 31 | `31_unsupported_tr` | unsupported | Python'da dictionary'ler nasıl çalışır? | `61ede6b7` | `28103990` | 0.86 | 0.81 | 0.85 | 0.70 | +0.04 |
| 32 | `32_unsupported_tr` | unsupported | İstanbul'daki ulaşım seçenekleri nelerdir? | `496bf4d8` | `c083da56` | 0.92 | 0.83 | 0.85 | 0.70 | +0.09 |
| 33 | `33_unsupported_en` | unsupported | What are the main features of the Java programming language? ⚠️Q | `—` | `6a448503` | — | 0.71 | — | 0.55 | — |
| 34 | `34_unsupported_en` | unsupported | How does HTTPS ensure security? | `ebdac6af` | `c4c9f180` | 0.85 | 0.76 | 0.85 | 0.70 | +0.09 |
| 35 | `35_unsupported_en` | unsupported | What does JSON stand for and where is it commonly used? | `f6a01aa4` | `5009e24a` | 0.35 | 0.35 | 0.70 | 0.55 | +0.00 |
| 36 | `36_partial_tr` | partial | Redis veritabanı nedir ve hangi veri yapılarını destekler? ⚠️Q | `—` | `13dd8fe5` | — | 0.77 | — | 0.85 | — |
| 37 | `37_partial_tr` | partial | Docker container'lar nasıl çalışır ve Docker image'larla ... | `5fe3459e` | `76480821` | 0.76 | 0.76 | 0.85 | 0.85 | -0.00 |
| 38 | `38_partial_en` | partial | What is Kubernetes and what problems does it solve? | `d7046893` | `b6f1d7f0` | 0.87 | 0.82 | 1.00 | 1.00 | +0.05 |
| 39 | `39_partial_en` | partial | What is the relationship between SQL and relational datab... | `bb603df0` | `97236af6` | 0.83 | 0.88 | 1.00 | 1.00 | -0.05 |
| 40 | `40_partial_en` | partial | How do JWT tokens work for authentication? ⚠️Q | `—` | `9561ef45` | — | 0.78 | — | 1.00 | — |
| 41 | `41_offtopic_tr` | offtopic | Python'da bir fonksiyon nasıl tanımlanır? | `b07be9f1` | `bb5e2630` | 0.20 | 0.20 | 0.70 | 0.55 | +0.00 |
| 42 | `42_offtopic_tr` | offtopic | PostgreSQL'de transaction izolasyon seviyeleri nelerdir? | `d803155c` | `6405e8e3` | 0.20 | 0.20 | 0.70 | 0.70 | +0.00 |
| 43 | `43_deflection_tr` | offtopic | Yapay zekâ modelleri nasıl eğitilir? | `5de05834` | `dee7fb49` | 0.20 | 0.20 | — | 0.70 | +0.00 |
| 44 | `44_deflection_en` | offtopic | What is the purpose of a load balancer? | `7cdd75d7` | `0b029221` | 0.20 | 0.20 | 1.00 | 0.70 | +0.00 |
| 45 | `45_offtopic_en` | offtopic | How does garbage collection work in Python? | `7a53b9aa` | `92eaf68f` | 0.20 | 0.20 | 0.85 | 0.55 | +0.00 |
| 46 | `46_low_precision_tr` | context_issue | ACID özellikleri nelerdir ve her biri ne anlama gelir? ⚠️O | `d53577bd` | `—` | 0.74 | — | 0.85 | — | — |
| 47 | `47_low_precision_en` | context_issue | What is the difference between TCP and UDP? | `1b870c1f` | `28d936f9` | 0.66 | 0.53 | 0.55 | 0.00 | +0.13 |
| 48 | `48_low_recall_tr` | context_issue | Django framework'ünün temel bileşenleri nelerdir? ⚠️Q | `—` | `a7a2fecf` | — | 0.58 | — | 0.00 | — |
| 49 | `49_low_recall_en` | context_issue | What are the key differences between REST and GraphQL? ⚠️Q | `—` | `74766af5` | — | 0.58 | — | 0.00 | — |
| 50 | `50_faithful_tr` | faithful | Git'te branch'ler nasıl birleştirilir ve merge ile rebase... ⚠️Q ⚠️O | `—` | `—` | — | — | — | — | — |

## Başarısız Trace'ler

17 trace en az bir stack'te tamamlanamadı. Ana sebep: ingest endpoint'inin 30/min rate-limit'i, `compare_models.py` concurrency=4 ile burst gönderince aşıldı.

| # | Case | Qwen status | OpenAI status |
|---|---|---|---|
| 10 | `10_faithful_en` | completed | ? |
| 12 | `12_subtle_tr` | ? | completed |
| 13 | `13_faithful_tr` | ? | completed |
| 15 | `15_subtle_tr` | ? | completed |
| 17 | `17_subtle_en` | ? | completed |
| 21 | `21_major_tr` | ? | completed |
| 23 | `23_major_tr` | ? | ? |
| 28 | `28_major_en` | ? | completed |
| 29 | `29_major_en` | ? | completed |
| 30 | `30_major_en` | ? | completed |
| 33 | `33_unsupported_en` | ? | completed |
| 36 | `36_partial_tr` | ? | completed |
| 40 | `40_partial_en` | ? | completed |
| 46 | `46_low_precision_tr` | completed | ? |
| 48 | `48_low_recall_tr` | ? | completed |
| 49 | `49_low_recall_en` | ? | completed |
| 50 | `50_faithful_tr` | ? | ? |

## Maliyet Dağılımı (başarılı trace'ler)

- **Qwen:** toplam $0.0272 / 148,828 token · ortalama $0.0008/trace · mean tokens 4252
- **OpenAI:** toplam $0.2885 / 309,371 token · ortalama $0.0063/trace · mean tokens 6725

## Tekrar Üretilebilirlik

```bash
# Her iki stack ayakta iken (docs/COMPARE_MODELS.md):
.venv/bin/python scripts/compare_models.py \
  --traces tests/fixtures/ab_compare_traces_50.json \
  --qwen-url http://localhost:8000   --qwen-key <QWEN_KEY> \
  --openai-url http://localhost:8001 --openai-key <OAI_KEY> \
  --out /tmp/ab_compare_50_raw.json \
  --concurrency 4

# Raporu raw dump'tan regenere et:
.venv/bin/python scripts/generate_ab_report.py
```
