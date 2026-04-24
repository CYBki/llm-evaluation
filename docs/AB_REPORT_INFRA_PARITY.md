# A/B Raporu — Infra Parity: Qwen-via-OR vs OpenAI-via-OR

Her iki stack de aynı gateway'i (OpenRouter) kullanır — tek değişken model ailesi. Bu run, [`AB_REPORT_QWEN_VS_OPENAI.md`](AB_REPORT_QWEN_VS_OPENAI.md) raporundaki 'OpenAI doğrudan `api.openai.com`' kurulumuna karşı **infra-eş** kontrol deneyidir. Fixture birebir aynı: [`tests/fixtures/ab_compare_traces_50.json`](../tests/fixtures/ab_compare_traces_50.json).

## Ayar Karşılaştırması

| | Qwen stack (port 8000) | OpenAI-via-OR stack (port 8002) |
|---|---|---|
| Gateway | OpenRouter | OpenRouter (aynı) |
| Stage 1 modeli | `qwen/qwen3-235b-a22b-2507` | `openai/gpt-5.2` |
| Stage 2 modeli | `qwen/qwen3-32b` | `openai/gpt-4o-mini` |
| RAG metrik modeli | `qwen/qwen3-32b` | `openai/gpt-5-mini` |
| Rate limit | 60/min | 60/min |
| Prompt / schema | aynı | aynı |

## Özet

- **Toplam trace:** 50
- **Her iki stack'te başarılı:** 28 (56%)
- **Maliyet:** Qwen **$0.0243** · OpenAI-via-OR **$0.0710** → 2.9× fark
- **Token:** Qwen 131,170 · OpenAI-via-OR 310,252
- **Ortalama süre:** Qwen 24466 ms · OpenAI-via-OR 18042 ms

## Metrik Bazlı İstatistik (infra-parity)

| Metrik | n | Qwen μ | OpenAI μ | Mean Δ | MAD | **Pearson** | Değerlendirme |
|---|--:|--:|--:|--:|--:|--:|---|
| `overall_score` | 28 | 0.571 | 0.594 | -0.023 | 0.030 | **0.923** | ✅ Mükemmel |
| `clarity` | 28 | 0.754 | 0.846 | -0.093 | 0.136 | **0.648** | 🟡 Orta |
| `coherence` | 28 | 0.807 | 0.879 | -0.071 | 0.093 | **0.802** | ✅ Çok iyi |
| `helpfulness` | 28 | 0.650 | 0.575 | +0.075 | 0.104 | **0.879** | ✅ Çok iyi |
| `completeness` | 28 | 0.500 | 0.518 | -0.018 | 0.185 | **0.703** | 🟡 İyi |
| `answer_relevancy` | 28 | 0.949 | 0.988 | -0.039 | 0.062 | **-0.076** | ❌ Düşük |
| `faithfulness` | 28 | 0.807 | 0.764 | +0.043 | 0.057 | **0.792** | 🟡 İyi |
| `hallucination_score` | 28 | 0.732 | 0.700 | +0.032 | 0.064 | **0.840** | ✅ Çok iyi |
| `context_precision` | 28 | 1.000 | 1.000 | +0.000 | 0.000 | **—** | — |
| `context_recall` | 28 | 1.000 | 1.000 | +0.000 | 0.000 | **—** | — |

## Trace-Bazlı Detay

| # | Case | Kategori | Qwen trace_id | OAI-OR trace_id | Qwen overall | OAI overall | Qwen hallu | OAI hallu | ΔOverall |
|---|---|---|---|---|--:|--:|--:|--:|--:|
| 1 | `01_faithful_tr` | faithful | `1abfea41` | `668c28d6` | 0.98 | 1.00 | 1.00 | 1.00 | -0.02 |
| 2 | `02_faithful_tr` | faithful | `36b5a196` | `0aef700d` | 0.96 | 0.96 | 1.00 | 1.00 | +0.00 |
| 3 | `03_faithful_tr` | faithful | `13bff57f` | `7169a975` | 0.96 | 1.00 | 1.00 | 1.00 | -0.04 |
| 4 | `04_faithful_tr` | faithful | `6a07ca7f` | `20db02db` | 0.93 | 0.96 | 1.00 | 1.00 | -0.04 |
| 5 | `05_faithful_tr` | faithful | `eb3cb597` | `0bf887e5` | 1.00 | 0.96 | 1.00 | 1.00 | +0.04 |
| 6 | `06_faithful_en` | faithful | `cf103182` | `d572da3c` | 0.92 | 0.92 | 0.85 | 0.85 | +0.00 |
| 7 | `07_faithful_en` | faithful | `a5932c03` | `13080216` | 0.96 | 0.96 | 1.00 | 1.00 | +0.00 |
| 8 | `08_faithful_en` | faithful | `6f915b75` | `ed3ce064` | 1.00 | 0.98 | 1.00 | 1.00 | +0.02 |
| 9 | `09_faithful_en` | faithful | `3692e89f` | `50e1dfcc` | 0.96 | 0.98 | 1.00 | 1.00 | -0.02 |
| 10 | `10_faithful_en` | faithful | `fff6e7a5` | `b24426b0` | 1.00 | 0.96 | 1.00 | 0.85 | +0.04 |
| 11 | `11_subtle_tr` | subtle | `6d19e2f9` | `bf37d76a` | 0.35 | 0.35 | 0.70 | 0.70 | +0.00 |
| 12 | `12_subtle_tr` | subtle | `b3f05d7c` | `88881783` | 0.35 | 0.35 | 0.70 | 0.70 | +0.00 |
| 13 | `13_faithful_tr` | faithful | `c3b3fafa` | `314daedf` | 0.35 | 0.98 | 0.70 | 1.00 | -0.63 |
| 14 | `14_subtle_tr` | subtle | `b19fe994` | `ba973b96` | 0.35 | 0.35 | 0.70 | 0.70 | +0.00 |
| 15 | `15_subtle_tr` | subtle | `9b8ca0fb` | `345d715f` | 0.35 | 0.35 | 0.70 | 0.70 | +0.00 |
| 16 | `16_subtle_en` | subtle | `68941e44` | `07da1b19` | 0.35 | 0.35 | 0.70 | 0.40 | +0.00 |
| 17 | `17_subtle_en` | subtle | `09eac035` | `807986b4` | 0.35 | 0.35 | 0.70 | 0.70 | +0.00 |
| 18 | `18_subtle_en` | subtle | `e5c0532f` | `9e8c5e84` | 0.35 | 0.35 | 0.70 | 0.55 | +0.00 |
| 19 | `19_subtle_en` | subtle | `41f1e470` | `cee69509` | 0.35 | 0.35 | 0.70 | 0.70 | +0.00 |
| 20 | `20_subtle_en` | subtle | `95a2d09c` | `86a31be0` | 0.35 | 0.35 | 0.70 | 0.70 | +0.00 |
| 21 | `21_major_tr` | major | `6761c8f7` | `56d1ff5f` | 0.35 | 0.35 | 0.55 | 0.55 | +0.00 |
| 22 | `22_major_tr` | major | `2009b93d` | `bf774cc9` | 0.35 | 0.35 | 0.40 | 0.40 | +0.00 |
| 23 | `23_major_tr` | major | `c358170f` | `7c3966f1` | 0.35 | 0.35 | 0.10 | 0.25 | +0.00 |
| 24 | `24_major_tr` | major ⚠️O | `cd8565d8` | `—` | 0.35 | — | 0.40 | — | — |
| 25 | `25_major_tr` | major | `0f252eb7` | `34192203` | 0.35 | 0.35 | 0.25 | 0.25 | +0.00 |
| 26 | `26_major_en` | major ⚠️O | `f86ca716` | `—` | 0.35 | — | 0.70 | — | — |
| 27 | `27_major_en` | major | `793f858c` | `ea792928` | 0.35 | 0.35 | 0.40 | 0.40 | +0.00 |
| 28 | `28_major_en` | major | `c98f4493` | `820be1c2` | 0.35 | 0.35 | 0.70 | 0.70 | +0.00 |
| 29 | `29_major_en` | major | `a0f048b1` | `b9ccbc94` | 0.35 | 0.35 | 0.55 | 0.40 | +0.00 |
| 30 | `30_major_en` | major | `189569ef` | `4402e84d` | 0.35 | 0.35 | 0.70 | 0.10 | +0.00 |
| 31 | `31_unsupported_tr` | unsupported ⚠️Q | `—` | `85f22c17` | — | 0.81 | — | 0.70 | — |
| 32 | `32_unsupported_tr` | unsupported ⚠️Q | `—` | `482305cd` | — | 0.81 | — | 0.70 | — |
| 33 | `33_unsupported_en` | unsupported ⚠️Q | `—` | `3187c981` | — | 0.66 | — | 0.55 | — |
| 34 | `34_unsupported_en` | unsupported ⚠️Q | `—` | `1f6e0104` | — | 0.73 | — | 0.70 | — |
| 35 | `35_unsupported_en` | unsupported ⚠️Q | `—` | `e0c76286` | — | 0.35 | — | 0.55 | — |
| 36 | `36_partial_tr` | partial ⚠️Q | `—` | `f0f5b895` | — | 0.76 | — | 0.85 | — |
| 37 | `37_partial_tr` | partial ⚠️Q | `—` | `86f53b1c` | — | 0.78 | — | 1.00 | — |
| 38 | `38_partial_en` | partial ⚠️Q | `—` | `5d0fa652` | — | 0.82 | — | 1.00 | — |
| 39 | `39_partial_en` | partial ⚠️Q | `—` | `dd101425` | — | 0.90 | — | 1.00 | — |
| 40 | `40_partial_en` | partial ⚠️Q | `—` | `fc6ff85d` | — | 0.80 | — | 1.00 | — |
| 41 | `41_offtopic_tr` | offtopic ⚠️Q | `—` | `f21cc135` | — | 0.20 | — | 0.55 | — |
| 42 | `42_offtopic_tr` | offtopic ⚠️Q | `—` | `e99c4f31` | — | 0.20 | — | 0.70 | — |
| 43 | `43_deflection_tr` | offtopic ⚠️Q | `—` | `5868cfab` | — | 0.20 | — | 0.70 | — |
| 44 | `44_deflection_en` | offtopic ⚠️Q | `—` | `57dae2bf` | — | 0.20 | — | 0.70 | — |
| 45 | `45_offtopic_en` | offtopic ⚠️Q | `—` | `3efc9f35` | — | 0.20 | — | 0.55 | — |
| 46 | `46_low_precision_tr` | context_issue ⚠️Q | `—` | `39ba5df9` | — | 0.57 | — | 0.25 | — |
| 47 | `47_low_precision_en` | context_issue ⚠️Q | `—` | `2d4e0908` | — | 0.53 | — | 0.00 | — |
| 48 | `48_low_recall_tr` | context_issue ⚠️Q | `—` | `15a829ca` | — | 0.58 | — | 0.00 | — |
| 49 | `49_low_recall_en` | context_issue ⚠️Q ⚠️O | `—` | `—` | — | — | — | — | — |
| 50 | `50_faithful_tr` | faithful ⚠️Q ⚠️O | `—` | `—` | — | — | — | — | — |

## Tekrar Üretilebilirlik

```bash
# Tüm üç stack ayakta iken:
.venv/bin/python scripts/compare_models.py \
  --traces tests/fixtures/ab_compare_traces_50.json \
  --qwen-url http://localhost:8000 --qwen-key <QWEN_KEY> \
  --openai-url http://localhost:8002 --openai-key <OAI_OR_KEY> \
  --out /tmp/ab_compare_50_or_raw.json \
  --concurrency 4
.venv/bin/python scripts/generate_infra_parity_report.py
```
