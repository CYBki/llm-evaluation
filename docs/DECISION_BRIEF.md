# Teknik Ekip Karar Dokümanı — LLM Evaluation Pipeline

> **Amaç:** Teknik ekibin bu dokümanı okuyup her başlık için **"evet / hayır / ertele"** kararı vermesi. Gerekçeler özet, detaylar referanslarda.

| Meta | |
|---|---|
| Hazırlayan | Migration test takımı |
| Tarih | 2026-04-24 |
| Branch | `feat/qwen-openrouter-migration` |
| Dayanak verilere referanslar | [TEST_LOG.md](TEST_LOG.md) · [AB_REPORT_QWEN_VS_OPENAI.md](AB_REPORT_QWEN_VS_OPENAI.md) · [AB_REPORT_INFRA_PARITY.md](AB_REPORT_INFRA_PARITY.md) · [AB_SUMMARY_3WAY.md](AB_SUMMARY_3WAY.md) · [COST_QUALITY_STRATEGY.md](COST_QUALITY_STRATEGY.md) |
| Toplam karar sayısı | 9 |
| Tahmini okuma süresi | 10-12 dk |

---

## TL;DR (1 dakika)

Migration branch'i 11 commit ile hazır. 50 trace iki ayrı A/B testinde
Qwen'in OpenAI ile **Pearson 0.92-0.99 uyumlu** olduğu doğrulandı.
**Maliyet 10-11× düşüyor.** Ek optimizasyonlarla bu oran 190×'e kadar
çıkabilir.

Ekipten **9 karar** istiyoruz. 3 tanesi bu hafta, 4 tanesi önümüzdeki
ay, 2 tanesi Q3 için.

| # | Karar | Önerim | Etki | Aciliyet |
|--:|---|---|---|---|
| 1 | Qwen'e geçiş (prod migration) | **Evet, staging'den başla** | $19k/yıl ↓ | **Bu hafta** |
| 2 | Provider pin (WandB/DeepInfra) | **Evet, tek satır env** | Uptime +%4, kalite ↑ | **Bu hafta** |
| 3 | Ground-truth sentinel set | **Evet, 50 trace etiketle** | Kalite gate aktive | **Bu hafta** |
| 4 | Cascade router | **Evet, Faz 2 olarak** | $900/yıl ek ↓ | 2-4 hafta |
| 5 | Prompt caching | **Evet, Faz 3** | $300/yıl ek ↓ | 4-6 hafta |
| 6 | Semantic dedup | **Ertele** | $200/yıl ek ↓ | Q3 |
| 7 | Distillation | **Ertele, araştır** | $450/yıl ek ↓ | Q4+ |
| 8 | Llama 3.3 70B alternatifi | **Hayır, şimdilik** | Belirsiz | — |
| 9 | Monitoring/alerting altyapısı | **Evet, Faz 2 ile birlikte** | Güvenlik | 2 hafta |

---

## KARAR 1 — Qwen Migration: Prod'a Çıkaralım mı?

### Bağlam

50 trace üzerinde iki A/B testi yaptık:

| Test | Ortak gateway mi? | overall_score Pearson |
|---|---|--:|
| T4 (direct) | Hayır — OpenAI `api.openai.com`, Qwen OpenRouter | **0.993** |
| T6 (parity) | Evet — ikisi de OpenRouter | **0.923** |

Kritik metriklerde (hallucination, faithfulness, overall) her iki modelin
kararları **yüksek korelasyonlu**. Qwen hallucination'ı sistematik olarak
biraz daha sıkı tespit ediyor (Qwen +0.03 ila +0.12 puan).

### Risk

- Ground truth yok — hangisi daha doğru kesin değil.
- 50 trace istatistik olarak sınırda.

### Seçenekler

| Seçenek | Açıklama | Risk |
|---|---|---|
| **A (öneri)** | Staging'e deploy, 2 hafta shadow mode, sonra %10 canary | Düşük, iptal kolay |
| B | Direkt %100 prod cutover | Yüksek |
| C | Başka modelde (Llama/DeepSeek) önce test | 2-4 hafta gecikme |
| D | Vazgeç, GPT kalsın | $19k/yıl kayıp |

### Öneri: **A — Staging shadow + kademeli canary**

2 hafta staging shadow, 1 hafta %10 canary, 1 hafta %50, son hafta %100.
Her aşamada overall_score Pearson ≥ 0.90 ve hallucination agreement ≥
%85 kontrol edilir.

### Karar

```
[ ] A — Staging shadow + kademeli canary (önerim)
[ ] B — Direkt cutover
[ ] C — Başka model önce test
[ ] D — Vazgeç

Karar veren: __________________  Tarih: __________
Notlar: ________________________________________________________________
```

---

## KARAR 2 — Provider Pinning

### Bağlam

Qwen3-235B OpenRouter'da **12 farklı provider**'da çalışıyor.
Quantization / uptime / fiyat ciddi farklar gösteriyor:

| Provider | Quant | Uptime 30g | Out $/M |
|---|---|--:|--:|
| WandB | **BF16** ⭐ | **99.84%** | $0.10 |
| DeepInfra | FP8 | 95.89% | $0.10 |
| Parasail | FP8 | 99.71% | $0.60 |
| ... | ... | ... | ... |
| Cerebras | FP16 | 100% | $1.20 |

Şu an OpenRouter otomatik seçiyor (çoğunlukla en ucuz = DeepInfra). Test
run'larımızda trace süresi 19s ↔ 25s arasında oynadı.

### Seçenekler

| Seçenek | Env değeri | Beklenen |
|---|---|---|
| **A (öneri)** | `wandb,deepinfra,parasail` | BF16 kalite, 99.84% uptime, $0.10 flat |
| B | `deepinfra` (tek) | En ucuz $0.07, tek nokta, 95.89% uptime |
| C | `cerebras` (hız için) | 12× pahalı, 100% uptime, çok hızlı |
| D | Boş bırak (şu an) | Belirsiz, non-deterministic |

### Öneri: **A — `wandb,deepinfra,parasail`**

WandB birincil (BF16 = daha kaliteli judge), DeepInfra ilk yedek (ucuz),
Parasail son yedek. Risk yok, tek satır env değişikliği, rollback
anında.

### Karar

```
[ ] A — wandb,deepinfra,parasail (önerim)
[ ] B — sadece DeepInfra
[ ] C — Cerebras pin (hız kritikse)
[ ] D — otomatik bırak

Karar veren: __________________  Tarih: __________
Notlar: ________________________________________________________________
```

---

## KARAR 3 — Ground-Truth Sentinel Set

### Bağlam

Şu an "Qwen ve OpenAI aynı karar veriyor" diyebiliyoruz ama "hangisi
doğru" diyemiyoruz. **Pearson=1 tuzağı:** iki judge birlikte yanılıyor
olabilir.

Çözüm: 30-50 trace'e **insan etiketi** koy. Her değişiklik (model,
cascade, cache) bu sete karşı accuracy ile test edilsin.

### İş Yükü

- 50 trace × ~3 dk insan değerlendirme ≈ 2.5 saat
- `tests/fixtures/sentinel_set.json` altında versiyon kontrollü
- Her release'de regresyon testi (CI'de zorunlu gate)

### Seçenekler

| Seçenek | Etki |
|---|---|
| **A (öneri)** | 50 trace etiketle, CI gate kur | Her değişiklikte kalite korunur |
| B | Sadece 15-20 trace (başlangıç) | Zayıf sinyal |
| C | Yapma | Her optimizasyon "umuyoruz ki" ile gidiyor |

### Öneri: **A — 50 trace sentinel set**

Bir kerelik 2.5 saat yatırım. Sonsuza kadar güvence.

### Karar

```
[ ] A — 50 trace etiketle + CI gate (önerim)
[ ] B — 15-20 trace yeter
[ ] C — Yapmayalım

Etiketleyecek kişi(ler): _______________________________________________
Teslim tarihi: __________________________________________________________
```

---

## KARAR 4 — Cascade Router Uygulama

### Bağlam

Trace'lerin %55'i basit (kolay faithful veya apaçık hallucination).
Bunlar için 235B model israf. Cheap (32B) model ile ön değerlendirme,
confidence düşükse expensive (235B) modele eskaletion.

**Beklenen:** $0.0005 → $0.000253 / trace (**%49 tasarruf**).

### İş Yükü

- Yeni modül `app/evaluation/cascade.py` — ~100 satır
- Rubric'e `confidence` alanı — 1 satır schema
- A/B test: 50 trace cascade vs baseline
- 1-2 hafta development + test

### Risk

- Cheap model yanlış değerlendirirse kalite düşer
- Azaltma: %5 shadow + sentinel gate + `CASCADE_ENABLED=false` bypass

### Merge kriteri (öneri)

- overall_score Pearson(cascade, baseline) ≥ **0.95**
- hallucination agreement rate ≥ **%90**
- En az %30 maliyet düşüşü
- Mevcut testler yeşil

### Seçenekler

| Seçenek | Zaman | Risk |
|---|---|---|
| **A (öneri)** | 2 hafta dev + 1 hafta shadow | Düşük (bypass flag) |
| B | Yapma, Qwen yeter | Kazanç kaçırılır |
| C | Q3'e ertele | Öncelik sorusu |

### Karar

```
[ ] A — Şimdi yap, Faz 2 olarak (önerim)
[ ] B — Yapma
[ ] C — Q3 sprint'e al

Sorumlu: ______________________   Merge target: __________________
Bütçe: ____ dev gün
```

---

## KARAR 5 — Prompt Caching

### Bağlam

Her evaluation prompt'u ~4000 token'lık sabit system prompt + rubric
içeriyor. Provider'lar (OpenRouter, DeepInfra, WandB, Anthropic) prompt
cache destekliyor — sabit kısma **%90 indirim**.

**Beklenen:** input cost %90 ↓ → toplam maliyetin %20-30'u.

### İş Yükü

- `app/evaluation/llm_client.py`'de mesajlara `cache_control` ekle
- 3-5 günlük dev
- Provider desteği test (WandB, DeepInfra)

### Risk

- Çok düşük. Provider cache desteklemese otomatik full pricing.

### Seçenekler

| Seçenek | Süre |
|---|---|
| **A (öneri)** | Cascade ile aynı sprint | 1 hafta |
| B | Ayrı sprint | 2 hafta (ama delay) |
| C | Yapma | ~$300/yıl kayıp |

### Karar

```
[ ] A — Cascade ile birlikte (önerim)
[ ] B — Ayrı sprint
[ ] C — Yapma

Karar: ______________________
```

---

## KARAR 6 — Semantic Deduplication Cache

### Bağlam

Production'da benzer/aynı trace'ler tekrar edebilir (%10-20 tahmin).
pgvector + embedding ile benzer sonuçları cache'ten dönersek o yüzde
kadar ücret ödemeyiz.

### İş Yükü

- PostgreSQL'e pgvector extension
- Embedding tabanlı lookup, TTL, cache invalidation
- 2-4 hafta dev + shadow test
- Rubric versiyonlama gerekli (bayat cache riski)

### Risk

- Orta. Yanlış eşleşme kalite düşürür.
- Cache invalidation mühendisliği yapılması zor bir iş.

### Öneri: **Ertele**

%10-20 tahmin production verisine dayanmıyor; önce **1 ay production
telemetri** alıp gerçek duplicate oranını ölçelim. Oran <%5 çıkarsa
ROI düşük.

### Seçenekler

| Seçenek | Zaman |
|---|---|
| **A (öneri)** | Q3 — telemetri sonrası | 1 ay bekle, sonra karar |
| B | Şimdi yap | Belirsiz ROI riski |
| C | Hiç yapma | $200/yıl kayıp, küçük |

### Karar

```
[ ] A — Q3'e ertele, önce telemetri (önerim)
[ ] B — Şimdi yap
[ ] C — İptal

Telemetri sorumlusu: __________________
```

---

## KARAR 7 — Distillation (7B öğrenci model)

### Bağlam

Qwen3-235B çıktılarıyla küçük bir model eğitip self-host → **%80 ek
tasarruf**. Ama 3-6 ay yatırım, GPU maliyeti, kalite drift riski.

### Öneri: **Ertele, Q4'te araştır**

Önce diğer optimizasyonlar bitsin. 1 yıl sonra Qwen4 gelebilir ya da
community distillation'ları hazır olabilir — kendimiz yatırım yapmadan
kazanç.

### Seçenekler

| Seçenek | Zaman | Yatırım |
|---|---|---|
| **A (öneri)** | Q4+ araştırma | 0 şimdilik |
| B | Şimdi başla | 3-6 ay + GPU $500-2000 + ekip |
| C | Hiç yapma | ~$450/yıl kaçırılır |

### Karar

```
[ ] A — Q4'e ertele, araştır (önerim)
[ ] B — Şimdi başla
[ ] C — Stratejik değil

Araştırma sahibi: __________________
Q4 gözden geçirme tarihi: __________________
```

---

## KARAR 8 — Llama 3.3 70B Alternatifi Test Edilsin mi?

### Bağlam

Qwen'den %30 daha ucuz olabilir ($0.07 vs $0.10) ama kalite testi yok.

### Risk

- Test yapmazsak $550/yıl kaçırmış olabiliriz.
- Test yaparsak (50 trace A/B) 1 gün çalışma + $1-2 maliyet + şu anki
  migration'ı geciktirir.

### Öneri: **Hayır, şimdilik**

Qwen migration stabilize olsun. 3 ay sonra baseline sağlamken Llama'yı
test edelim. O sırada Llama 3.4 veya 4 gelmiş olabilir — tekrar test
zaten gerekecek.

### Seçenekler

| Seçenek | Zaman | Kazanç potansiyeli |
|---|---|---|
| **A (öneri)** | 3 ay sonra | Belirsiz |
| B | Şimdi test et | Migration'ı geciktirir |
| C | Hiç test etme | $550/yıl potansiyel kayıp |

### Karar

```
[ ] A — 3 ay sonra (önerim)
[ ] B — Şimdi test
[ ] C — İptal

Karar: __________________
```

---

## KARAR 9 — Monitoring / Alerting Altyapısı

### Bağlam

Migration sonrası kalite/maliyet sürekli izlenmeli. Şu an Grafana yok,
custom alert yok.

### Gerekenler (minimum)

| Metrik | Nerede | Alarm eşiği |
|---|---|---|
| overall_score avg (günlük) | Grafana | Δ > 0.05 hafta/hafta |
| hallucination flag agreement (shadow) | Grafana | < %85 |
| cost_usd (günlük) | Grafana | > $10/gün beklenmiyorken |
| evaluation_duration p95 | Grafana | > 30s |
| error_rate | Grafana | > %5 |
| OpenRouter provider used | log | (raporlama için) |

### İş Yükü

- Prometheus + Grafana docker-compose'a eklenir
- 5-8 custom query + dashboard
- Alertmanager + Slack webhook
- ~1 hafta dev

### Seçenekler

| Seçenek | Zaman | Etki |
|---|---|---|
| **A (öneri)** | Faz 2 (cascade) ile birlikte, 1 hafta | Kalite/maliyet görünür |
| B | Migration'dan önce | 1 hafta gecikme |
| C | Sonra | Kör uçuş, risk |

### Karar

```
[ ] A — Cascade ile birlikte (önerim)
[ ] B — Önce yap, sonra migration
[ ] C — Sonra

Sorumlu: __________________
Stack: Prometheus + Grafana mı yoksa Datadog mı?: __________________
```

---

## Konsolide Rollout Planı (önerilerim onaylanırsa)

```
Hafta 1 (bu hafta)
├─ KARAR 1A: Staging'e deploy
├─ KARAR 2A: Provider pin env güncelle
└─ KARAR 3A: Sentinel set etiketleme başla (2.5 saat insan işi)

Hafta 2-3
├─ Staging shadow mode (%100 paralel)
└─ KARAR 3: Sentinel set tamamlandı → CI gate aktif

Hafta 4 (canary)
├─ %10 production traffic Qwen'e
└─ KARAR 9A: Monitoring/alerting hazır

Hafta 5-6
├─ %50 → %100 cutover
└─ KARAR 4 (cascade) dev başlar

Hafta 7-8
├─ KARAR 4: Cascade ship
└─ KARAR 5 (prompt caching) dev

Hafta 9-10
└─ KARAR 5: Prompt caching ship

Q3 checkpoint
├─ Telemetri review
├─ KARAR 6 (semantic dedup) kararı ver
└─ KARAR 8 (Llama alternatif) kararı ver

Q4 checkpoint
└─ KARAR 7 (distillation) araştırma review
```

---

## Finansal Özet (önerilen yol izlenirse)

| Durum | $/trace | Yıllık |
|---|--:|--:|
| Bugün (GPT) | $0.2885 | $21,060 |
| Hafta 6 sonu (Qwen only) | $0.00050 | $1,825 |
| Hafta 10 sonu (cascade + cache) | $0.00018 | $657 |
| Q4 sonu (distillation varsa) | $0.00003 | $110 |

**İlk 10 haftada $19,400/yıl tasarruf kilitlenmiş olur.**

---

## Kararları Kim Verir?

| Karar | Önerilen yetki |
|---|---|
| 1 (migration) | Head of Engineering + Product |
| 2 (provider pin) | Tech Lead |
| 3 (sentinel set) | Tech Lead + QA |
| 4 (cascade) | Tech Lead |
| 5 (prompt cache) | Tech Lead |
| 6 (semantic cache) | Tech Lead + Head of Engineering |
| 7 (distillation) | Head of Engineering + Head of Product |
| 8 (Llama alt.) | Tech Lead |
| 9 (monitoring) | Tech Lead + DevOps |

---

## Referanslar

- [TEST_LOG.md](TEST_LOG.md) — 6 testin kronolojik kaydı
- [AB_REPORT_QWEN_VS_OPENAI.md](AB_REPORT_QWEN_VS_OPENAI.md) — 50 trace direct A/B, per-metric Pearson/MAD
- [AB_REPORT_INFRA_PARITY.md](AB_REPORT_INFRA_PARITY.md) — 50 trace infra-parity A/B
- [AB_SUMMARY_3WAY.md](AB_SUMMARY_3WAY.md) — direct vs parity delta, maliyet karşılaştırması
- [COST_QUALITY_STRATEGY.md](COST_QUALITY_STRATEGY.md) — 5 katmanlı optimizasyon tasarımı (detaylı gerekçeler)
- [COMPARE_MODELS.md](COMPARE_MODELS.md) — A/B script kullanım rehberi

---

## Ekip İmzaları

```
Karar verenler okuduğunda aşağıya imza / initial bırakılır:

[ ] Head of Engineering      ____________________ Tarih: __________

[ ] Tech Lead                ____________________ Tarih: __________

[ ] Head of Product          ____________________ Tarih: __________

[ ] DevOps Lead              ____________________ Tarih: __________

[ ] QA Lead                  ____________________ Tarih: __________

Toplantı tarihi: __________________________________
Karar özeti (sekreter):
  ____________________________________________________________________
  ____________________________________________________________________
  ____________________________________________________________________
```
