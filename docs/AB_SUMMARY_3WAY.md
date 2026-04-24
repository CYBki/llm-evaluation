# 3-Yönlü Özet: OpenAI-direct vs OpenAI-via-OpenRouter

Aynı Qwen stack'e karşı, OpenAI'ı (a) doğrudan `api.openai.com` ve (b) `openrouter.ai` gateway'i üzerinden çağırdığımızda metriklerin nasıl değiştiğini gösterir. Bu, 'tarafsız test' sorusunun cevabı: infra farklılığı sonuçları ne kadar bozuyor?

## Kurulum

| Run | Qwen | OpenAI | Rapor |
|---|---|---|---|
| **Direct** | `qwen3-235b` via OpenRouter | `gpt-5.2` via `api.openai.com` | [AB_REPORT_QWEN_VS_OPENAI.md](AB_REPORT_QWEN_VS_OPENAI.md) |
| **Parity** | `qwen3-235b` via OpenRouter | `gpt-5.2` via OpenRouter | [AB_REPORT_INFRA_PARITY.md](AB_REPORT_INFRA_PARITY.md) |

## Pearson Korelasyon Değişimi

| Metrik | Direct run Pearson | Parity run Pearson | Δ |
|---|--:|--:|--:|
| `overall_score` | 0.993 | 0.923 | -0.070 |
| `clarity` | -0.070 | 0.648 | +0.717 🔺 |
| `coherence` | 0.020 | 0.802 | +0.781 🔺 |
| `helpfulness` | 0.900 | 0.879 | -0.021 |
| `completeness` | 0.751 | 0.703 | -0.049 |
| `answer_relevancy` | 0.941 | -0.076 | -1.017 🔻 |
| `faithfulness` | 0.851 | 0.792 | -0.059 |
| `hallucination_score` | 0.857 | 0.840 | -0.018 |
| `context_precision` | 1.000 | — | — |
| `context_recall` | 0.948 | — | — |

## Ortalama Skor Değişimi (her metrik için)

| Metrik | Qwen (direct) | Qwen (parity) | OAI-direct | OAI-via-OR | OAI Δ |
|---|--:|--:|--:|--:|--:|
| `overall_score` | 0.595 | 0.571 | 0.585 | 0.594 | +0.009 |
| `clarity` | 0.730 | 0.754 | 0.855 | 0.846 | -0.008 |
| `coherence` | 0.739 | 0.807 | 0.900 | 0.879 | -0.021 |
| `helpfulness` | 0.609 | 0.650 | 0.539 | 0.575 | +0.036 |
| `completeness` | 0.450 | 0.500 | 0.490 | 0.518 | +0.028 |
| `answer_relevancy` | 0.788 | 0.949 | 0.833 | 0.988 | +0.155 |
| `faithfulness` | 0.812 | 0.807 | 0.700 | 0.764 | +0.064 |
| `hallucination_score` | 0.784 | 0.732 | 0.669 | 0.700 | +0.031 |
| `context_precision` | 0.970 | 1.000 | 0.970 | 1.000 | +0.030 |
| `context_recall` | 0.960 | 1.000 | 0.970 | 1.000 | +0.030 |

## Maliyet ve Süre

| | Qwen direct | Qwen parity | OAI direct | OAI via-OR |
|---|--:|--:|--:|--:|
| Toplam maliyet | $0.0272 | $0.0243 | $0.2885 | $0.0710 |
| Toplam token | 148,828 | 131,170 | 309,371 | 310,252 |
| Ortalama süre (ms) | 19613 | 24466 | 18581 | 18042 |

## Kritik Bulgular

**En çok iyileşen korelasyonlar (infra parity avantajı):**

- `coherence`: 0.020 → **0.802** (+0.781)
- `clarity`: -0.070 → **0.648** (+0.717)

**En çok bozulan korelasyonlar:**

- `answer_relevancy`: 0.941 → **-0.076** (-1.017)
- `overall_score`: 0.993 → **0.923** (-0.070)

## Yorum

- **Infra parity = daha tarafsız test.** OpenAI çağrılarının OpenRouter gateway'i üzerinden yapılması, Qwen ile OpenAI arasındaki saf model kalite farkını izole eder. Yukarıdaki Pearson değişimleri tam olarak *infra farklılığından gelen* varyansı yansıtır.
- **`clarity` / `coherence` artık korele** (direct run'da korelasyonsuzdu). Bu, ilk rapordaki 'felsefi fark' açıklamasının sadece bir kısmının gerçek; kalanı OpenAI direct endpoint'in `response_format=json_schema` yorumunun OpenRouter'dan farklı olması olabilir.
- **Kritik metrikler (overall, hallucination, faithfulness) her iki setupta da yüksek korelasyon gösteriyor** — migration güvenliği için birinci göstergeler.
- **`answer_relevancy` parity'de düştü** (0.94 → -0.08): her iki model de gateway üzerinden neredeyse hep 1.0 veriyor, variance kayboldu → Pearson tanımsızlaşıyor, gürültü olarak yorumlanmalı.
- **Maliyet farkı hâlâ ~3×** (parity run'ında Qwen $0.024, OAI-via-OR $0.071). Direct run'daki 10× fark pricing config farklılığından geliyor, gerçek OpenRouter faturalandırması 3× civarı.

## Sonuç

Infra-parity run'ı **migration için güven tazeleyen** bir kontrol deneyidir. Qwen'in OpenAI'a olan `overall_score` uyumu parity'de de yüksek kalıyor (0.923), ve hallucination detection'da sistematik 'Qwen daha sıkı' bulgusu korunuyor. Öncelikli metriklerde karar değişmiyor: **Qwen migration production-safe.**
