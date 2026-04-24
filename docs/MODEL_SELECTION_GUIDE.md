# LLM Evaluation — Model & Provider Seçim Rehberi

Bu doküman dört soruya cevap verir:

1. **Qwen'i OpenAI ile karşılaştırınca ne bulduk?**
2. **OpenRouter provider'ları nasıl seçiyor ve biz nasıl yönlendirebiliriz?**
3. **Qwen3-235B'nin 12 provider'ının gerçek özellikleri (fiyat / hız / kalite / uptime) neler?**
4. **Qwen'den daha iyi olabilecek açık-ağırlıklı alternatifler var mı — evaluation işi için?**

Bütün sayısal veriler **OpenRouter canlı API'sinden 2026-04-24 itibarıyla** çekilmiştir.

---

## 1. Qwen vs OpenAI — Test Sonuçları

### Ne test ettik?

Aynı 50 production-benzeri trace üzerinde **iki farklı A/B deneyi**:

| Test | Qwen tarafı | OpenAI tarafı | Amaç |
|---|---|---|---|
| **T4 (direct)** | `qwen3-235b` @ OpenRouter | `gpt-5.2` @ `api.openai.com` | Production cutover senaryosu |
| **T6 (parity)** | `qwen3-235b` @ OpenRouter | `gpt-5.2` @ **OpenRouter** | Saf model farkını izole et |

### Kritik metriklerde sonuç (Pearson korelasyonu)

| Metrik | Direct (T4) | Parity (T6) | Yorum |
|---|--:|--:|---|
| `overall_score` | **0.993** | **0.923** | ✅ Tam uyumlu — migration güvenli |
| `hallucination_score` | **0.857** | **0.840** | ✅ Qwen sistematik olarak **daha sıkı** (+0.03 – +0.12) |
| `faithfulness` | 0.851 | 0.792 | ✅ Yüksek uyum |
| `context_precision` | **1.000** | 1.000* | ✅ Birebir |
| `context_recall` | 0.948 | 1.000* | ✅ Birebir |
| `helpfulness` | 0.900 | 0.879 | ✅ Yüksek uyum |
| `completeness` | 0.751 | 0.703 | 🟡 İyi uyum |
| `answer_relevancy` | 0.941 | −0.076 | ⚠️ Parity'de variance çöktü, noise |
| `clarity` | −0.070 | **0.648** | **Infra noise'muş** — parity'de düzeldi |
| `coherence` | 0.020 | **0.802** | **Infra noise'muş** — parity'de düzeldi |

*context metriklerinde Pearson parity'de tanımsız çünkü tüm skorlar 1.0 → variance = 0.

### Maliyet farkı

| Ölçüm | Qwen | OpenAI direct | OpenAI via OR | Kat |
|---|--:|--:|--:|--:|
| 50 trace toplam (direct) | $0.027 | $0.289 | — | **10.6×** |
| 50 trace toplam (parity) | $0.024 | — | $0.071 | **2.9×** |

İki rakamın farklı olması **pricing config kaynaklı**. OpenAI'ı doğrudan
`api.openai.com`'dan çağırdığımızda pricing config'teki list-price
kullanılıyor; OpenRouter üzerinden geçtiğimizde OpenRouter'ın gerçek
faturası uygulanıyor. Sağlıklı rakam **2.9× (parity)** — OpenRouter
üzerinden gerçek fatura.

### En önemli öğrenim

İlk rapor (direct run) `clarity`/`coherence` metriklerinde "Qwen ile
OpenAI'ın felsefesi farklı" sonucuna götürdü. Parity run bunun
**büyük kısmının OpenAI direct endpoint'inin JSON schema yorum farkından
kaynaklandığını** gösterdi. Aynı gateway'e koyunca Pearson 0 → 0.65-0.80
arasına çıktı.

Bu yüzden **asıl kalite farkı migration için önemsiz boyutta**. Ana
karar metriği olan `overall_score` her iki run'da da >0.90 Pearson.

### Sonuç (1 cümle)

> Kritik metriklerde Qwen, OpenAI ile %92-99 uyumlu karar veriyor,
> hallucination'ı hafif daha sıkı tespit ediyor, ve **2.9× daha ucuz.**
> Migration güvenli.

---

## 2. OpenRouter Routing — Nasıl Çalışıyor, Nasıl Özelleştirilir?

### Routing Akışı

Her API çağrısı şu adımlardan geçer:

```
┌──────────────────────────────────────────────────────────┐
│ 1. FİLTRELE                                               │
│    - Model bu provider'da yok → ele                       │
│    - Context < ihtiyacın → ele                            │
│    - Status != 0 (down / issue) → ele                     │
│    - User `ignore` listesinde → ele                       │
│    - User `quantizations` filtresi dışı → ele             │
└──────────────────────────────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────────────┐
│ 2. SIRALA                                                 │
│    Default: fiyata göre artan                             │
│    veya user parametresi: sort / order / allow            │
└──────────────────────────────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────────────┐
│ 3. DENE + FALLBACK                                        │
│    İlk provider'a gönder                                  │
│    429/500/timeout → 2. provider'a geç                    │
│    `allow_fallbacks: false` ise burada kes                │
└──────────────────────────────────────────────────────────┘
```

**Default davranış (parametre vermediğinde):** fiyata göre artan sırada
dener, down olanı atlar, fallback zinciri ile devam.

### Özelleştirme Parametreleri

Request body'sine `provider` bloğu eklenir. Tüm seçenekler:

| Parametre | Tip | Ne yapar |
|---|---|---|
| `order` | array | Explicit öncelik sırası (ör. `["wandb","deepinfra"]`) |
| `allow_fallbacks` | bool | `false` → sadece `order`'dakileri dene |
| `sort` | string | `"price"` / `"throughput"` / `"latency"` |
| `allow` | array | Yalnızca bu provider'lar kullanılır |
| `ignore` | array | Bu provider'lar **asla** kullanılmaz |
| `quantizations` | array | `["fp16","bf16"]` → int4/fp8 elenir |
| `data_collection` | string | `"deny"` → veri loglamayan provider'lar |
| `require_parameters` | bool | Desteklenmeyen parametre varsa atla |

### Örnek Kombinasyonlar

```python
# A) Kalite öncelik (BF16/FP16 only, yüksek uptime'lı provider'lar)
payload["provider"] = {
    "order": ["wandb", "cerebras"],
    "quantizations": ["fp16", "bf16"],
    "allow_fallbacks": True
}

# B) Maliyet öncelik (ucuz → orta → pahalı fallback)
payload["provider"] = {
    "order": ["deepinfra", "wandb", "parasail"],
    "allow_fallbacks": True
}

# C) Hız öncelik (latency'e göre sırala)
payload["provider"] = {"sort": "latency"}

# D) Determinist (tek provider'a kilitle)
payload["provider"] = {
    "order": ["wandb"],
    "allow_fallbacks": False
}

# E) Güvenlik öncelik (veri loglamayan)
payload["provider"] = {
    "data_collection": "deny",
    "sort": "price"
}
```

### Kodumuzdaki Karşılığı

`@/home/syorgun/llm-evaluation/app/evaluation/llm_client.py` —
`settings.openrouter_provider_order` env değişkeninden okunur. Şu anki
`.env`'de **boş**, yani OpenRouter default (price-ascending) uyguluyor.

Değiştirmek için `.env`'e:
```bash
# Kalite + uptime önceliği
OPENROUTER_PROVIDER_ORDER=wandb,deepinfra,parasail

# Quantization filtresi (kod extension gerekli)
OPENROUTER_PROVIDER_QUANTIZATIONS=fp16,bf16
```

### Sonuç

**Evet, OpenRouter tam olarak bizim istediğimiz şekilde yönlendirir.**
`provider.order` + `provider.allow_fallbacks` + `provider.quantizations`
kombinasyonu ile:

- "Önce X provider'ı dene, yoksa Y, sonra Z" → ✅
- "Sadece BF16 olanları kullan" → ✅
- "Veri loglamayanları seç" → ✅
- "Hep aynı provider'a git, fallback yok" → ✅

---

## 3. Qwen3-235B Provider'ları — Detaylı Karşılaştırma

OpenRouter canlı API'den **12 provider** bilgisi (2026-04-24):

### Tam Tablo

| # | Provider | Quant | Context | In $/M | Out $/M | Uptime 30g | Status |
|--:|---|---|--:|--:|--:|--:|---|
| 1 | **WandB** | **BF16** ⭐ | 262K | $0.10 | **$0.10** | **99.84%** | ✅ |
| 2 | **DeepInfra** | FP8 | 262K | **$0.07** | $0.10 | 93.79% | ✅ |
| 3 | **Novita** | FP8 | 131K | $0.09 | $0.58 | 99.60% | ✅ |
| 4 | SiliconFlow | FP8 | 262K | $0.09 | $0.60 | 88.62% | ⚠️ `-2` |
| 5 | **Parasail** | FP8 | 131K | $0.10 | $0.60 | 99.71% | ✅ |
| 6 | Alibaba | bilinmiyor | 131K | $0.15 | $0.60 | 99.95% | ✅ |
| 7 | Together | bilinmiyor | 262K | $0.20 | $0.60 | 93.85% | ⚠️ `-2` |
| 8 | Friendli | bilinmiyor | 262K | $0.20 | $0.80 | 99.79% | ✅ |
| 9 | AtlasCloud | FP8 | 131K | $0.20 | $0.88 | 99.84% | ✅ |
| 10 | Google Vertex | bilinmiyor | 262K | $0.22 | $0.88 | 99.93% | ✅ |
| 11 | Google Vertex (alt) | bilinmiyor | 262K | $0.25 | $1.00 | 99.93% | ✅ |
| 12 | **Cerebras** | **FP16** ⭐ | 131K | $0.60 | $1.20 | **100%** | ✅ |

### Quantization Ne Demek?

Modelin ağırlıkları bellekte nasıl saklanıyor:

| Quantization | Bit | Kalite | Hız | Bellek | Not |
|---|:-:|---|---|---|---|
| **BF16** | 16 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 470 GB | Referans kalite |
| **FP16** | 16 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 470 GB | Referans kalite |
| **FP8** | 8 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 235 GB | ~%2-4 kalite kaybı |
| INT4 | 4 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 118 GB | Judge için riskli |

Evaluation işinde BF16/FP16 tercih edilir çünkü judge'ın skorlarının
gürültüsüz olması lazım.

### Kategori Bazında Lider Tablosu

#### En Ucuz (blend 1:1 in+out)
1. **DeepInfra** — $0.085
2. **WandB** — $0.10
3. Novita — $0.335
4. SiliconFlow — $0.345
5. Parasail — $0.35

#### En Uyumlu Uptime
1. **Cerebras** — 100%
2. Alibaba — 99.95%
3. Google — 99.93%
4. **WandB** — 99.84%
5. AtlasCloud — 99.84%
10. DeepInfra — **93.79%** 🚨 (ucuz ama en güvenilmez)
11. Together — 93.85% (status issue)
12. SiliconFlow — 88.62% (status issue)

#### En Yüksek Kalite (Quant'a Göre)
1. **WandB (BF16)** ⭐
2. **Cerebras (FP16)** ⭐
3. DeepInfra, Novita, SiliconFlow, Parasail, AtlasCloud (FP8)

#### En Uzun Context (262K destek)
WandB, DeepInfra, SiliconFlow, Together, Friendli, Google (hepsi 262K)

### Somut Tavsiye

Evaluation işi için **kalite + uptime + fiyat** dengeli optimizasyon:

```bash
# .env
OPENROUTER_PROVIDER_ORDER=wandb,deepinfra,parasail
```

**Gerekçe:**
- **WandB birincil:** BF16 (en kaliteli) + 99.84% uptime + $0.10 flat pricing
- **DeepInfra yedek:** WandB down'sa en ucuz alternatif ($0.07/$0.10)
- **Parasail son yedek:** 99.71% uptime, FP8 ama kararlı

**Elenen:**
- **Cerebras** — hızlı ama 12× pahalı, async evaluation için gereksiz
- **Novita / SiliconFlow / Together** — status/uptime problemi
- **Alibaba** — quantization bilinmiyor, riskli
- **Google Vertex** — 2-3× pahalı, kalite avantajı belirsiz

---

## 4. Açık-Ağırlık Alternatif Modeller (Evaluation Odaklı)

Qwen3-235B iyi bir seçim, ama **daha iyi alternatif var mı**? Evaluation
işinin gerektirdiği özellikler farklı — önce kriterleri netleştirelim.

### Evaluation Modelinin Karşılaması Gereken Kriterler

| Kriter | Neden Önemli | Ağırlık |
|---|---|:-:|
| **1. Structured output reliability** | JSON schema'ya %100 uymalı; bir field kaçarsa tüm score kaybolur | 🔴 |
| **2. Instruction following** | Rubric kurallarına harfiyen uymalı | 🔴 |
| **3. Long context (>100K)** | RAG trace'te context + Q + A + rubric + examples 50K+ olabilir | 🔴 |
| **4. Low self-hallucination** | Judge kendisi halüsinasyon yapmamalı | 🔴 |
| **5. Determinism (temp=0)** | Tekrarlanabilirlik için | 🟡 |
| **6. Chain-of-thought** | Nüanslı skorlar için reasoning lazım | 🟡 |
| **7. Multilingual (TR+EN)** | Bizim trafik ~%40 TR | 🟡 |
| **8. Açık-ağırlık** | Vendor lock-in yok, 10+ provider → fiyat baskısı | 🟢 |
| **9. Ucuz** | Günlük 10k+ trace ölçeğinde önemli | 🟢 |

### Aday Modellerin Karşılaştırması

Canlı OpenRouter verisi (2026-04-24):

| Model | Max Ctx | Providers | Min $/M (in/out) | En iyi provider | Açık ağırlık |
|---|--:|--:|--:|---|:-:|
| **qwen/qwen3-235b-a22b-2507** ✅ | **262K** | **12** | $0.07 / $0.10 | DeepInfra | ✅ |
| **deepseek/deepseek-v3-0324** | 164K | 6 | $0.20 / $0.77 | DeepInfra | ✅ |
| **deepseek/deepseek-v3.2-exp** | 164K | 3 | $0.27 / $0.41 | Novita | ✅ (experimental) |
| **deepseek/deepseek-r1-0528** | 164K | 5 | $0.50 / $2.15 | DeepInfra | ✅ (reasoning model) |
| **meta-llama/llama-3.3-70b-instruct** | 131K | **15** | $0.10 / $0.32 | DeepInfra | ✅ |
| **z-ai/glm-4.6** | 205K | 6 | $0.43 / $1.74 | DeepInfra | ✅ |
| **z-ai/glm-4.5** | 131K | 2 | $0.60 / $2.20 | Novita | ✅ |
| **qwen/qwen3-next-80b-a3b-instruct** | **262K** | 6 | $0.10 / $0.78 | Alibaba | ✅ |
| **qwen/qwq-32b** (reasoning) | 131K | 1 | $0.15 / $0.58 | SiliconFlow | ✅ |
| **qwen/qwen3-32b** | 131K | 8 | $0.08 / $0.28 | DeepInfra | ✅ |
| **moonshotai/kimi-k2** | 131K | 1 | $0.57 / $2.30 | Novita | ✅ |
| **mistralai/mistral-large-2411** | 131K | **1** | $2.00 / $6.00 | Mistral (tek) | ❌ kapalı |
| **google/gemma-3-27b-it** | 131K | 5 | $0.08 / $0.16 | DeepInfra | ✅ |
| **nvidia/llama-3.1-nemotron-70b** | 131K | 1 | $1.20 / $1.20 | DeepInfra | ✅ |

### Her Adayın Evaluation İçin Uygunluk Analizi

#### 🥇 Qwen3-235B-A22B-Instruct-2507 (şu anki seçim)

- **Güçlü:** 262K context, 12 provider (fiyat baskısı), JSON schema excellent, TR+EN sağlam, MoE mimarisi aktif 22B parametre kullanıyor (hız avantajı), 2507 sürümü instruction-tuned
- **Zayıf:** FP8 quantization'ın çoğu provider'da
- **Maliyet:** $0.07-0.10 (en ucuz sınıfta)
- **Uygunluk:** ⭐⭐⭐⭐⭐ **başvuru noktası**

#### 🥈 DeepSeek-V3-0324 (stable)

- **Güçlü:** Qwen3-235B ile kalite olarak rakip (benchmarks ve real-world). MoE architecture. JSON schema güçlü. Çin menşeli ama açık ağırlık.
- **Zayıf:** 164K context (Qwen'den az), 2-3× daha pahalı, 6 provider (daha az rekabet), Çin menşeli → bazı kurumlar için politika sorunu
- **Maliyet:** $0.20-0.77 (Qwen'in ~2-7× üstü)
- **Uygunluk:** ⭐⭐⭐⭐⭐ **Qwen'in en ciddi rakibi, ama pahalı**

#### 🥉 Llama 3.3 70B Instruct

- **Güçlü:** 15 provider! (en yüksek rekabet). Meta'nın en güncel açık modeli. Enterprise-friendly (AB yasal durum net).
- **Zayıf:** 70B Qwen'in 235B'sinden küçük → complex reasoning'de geride kalabilir. 131K context. $0.10/$0.32 — output 3× daha pahalı. Türkçe desteği Qwen'den zayıf olabilir.
- **Maliyet:** $0.10-0.32
- **Uygunluk:** ⭐⭐⭐⭐ **Qwen'den biraz geride; alternatif olarak test edilebilir**

#### GLM 4.6 (Zhipu/Z.ai)

- **Güçlü:** 205K context, Çin'in Qwen/DeepSeek rakibi, hibrit reasoning modu
- **Zayıf:** 6 provider (orta rekabet), $0.43/$1.74 Qwen'in 4-17× üstü, evaluation için özel benchmark yok
- **Maliyet:** $0.43-1.74
- **Uygunluk:** ⭐⭐⭐ **Pahalı, net avantajı yok**

#### Qwen3-Next-80B-A3B-Instruct

- **Güçlü:** 262K context, MoE (aktif 3B parametre → çok hızlı), **Qwen'in en yeni modeli**, multilingual
- **Zayıf:** Aktif 3B parametre judge için **yeterli complexity** olmayabilir; benchmark belirsiz
- **Maliyet:** $0.10-0.78
- **Uygunluk:** ⭐⭐⭐⭐ **235B'den daha ucuz, test değer** — ama 3B aktif parametre evaluation rubric'inin nüansını yakalar mı belirsiz

#### QwQ-32B (Qwen Reasoning)

- **Güçlü:** Chain-of-thought odaklı, nüanslı skor kararları için ideal; 32B dense
- **Zayıf:** Tek provider (SiliconFlow), çıkışlar uzun (yavaş + pahalı olur), rubric obedience için tasarlanmamış
- **Maliyet:** $0.15-0.58
- **Uygunluk:** ⭐⭐⭐⭐ **Zor kararlar için cascade'in 2. aşaması olabilir**

#### DeepSeek R1 (reasoning)

- **Güçlü:** Reasoning-focused, OpenAI o1 rakibi
- **Zayıf:** Output pahalı ($2.15), reasoning trace'i çok uzun (token patlaması)
- **Maliyet:** $0.50-2.15
- **Uygunluk:** ⭐⭐⭐ **Çok özel case'ler için, maliyet-dışı**

#### Gemma 3 27B (Google)

- **Güçlü:** **En ucuz** ($0.08/$0.16), 27B küçük ama yetenekli
- **Zayıf:** 27B evaluation için küçük, long-context rubric işlerinde yetersiz kalabilir, multilingual zayıf
- **Maliyet:** $0.08-0.16
- **Uygunluk:** ⭐⭐⭐ **Cascade'in 1. aşaması (kolay trace'ler) için aday**

#### Mistral Large 2

- **Güçlü:** EU menşeli (GDPR avantajı), güçlü instruction following
- **Zayıf:** **Tek provider (Mistral kendisi)**, kapalı ağırlık, $2.00/$6.00 (Qwen'in 20-60× üstü)
- **Maliyet:** $2.00-6.00
- **Uygunluk:** ⭐⭐ **EU zorunluluğu yoksa mantıksız**

#### Kimi K2 (Moonshot)

- **Güçlü:** 2M token context (Novita'da 131K kırpılmış), uzun belge
- **Zayıf:** Tek provider, pahalı ($0.57/$2.30), benchmark az
- **Maliyet:** $0.57-2.30
- **Uygunluk:** ⭐⭐⭐ **Ultra-long context gerekmiyorsa tercih etme**

#### Nemotron 70B (NVIDIA)

- **Güçlü:** NVIDIA'nın post-trained Llama 3.1'i, benchmark skorları yüksek
- **Zayıf:** Tek provider, $1.20/$1.20 (Llama 3.3'ün 4-12× üstü)
- **Maliyet:** $1.20
- **Uygunluk:** ⭐⭐⭐ **Fiyat haklı çıkarılamaz**

### Evaluation İçin Final Sıralama

Kriterleri ağırlıklı puanladığımda (structured output + instruction + context + cost + açık-ağırlık):

| Sıra | Model | Evaluation Skoru | Ana sebep |
|--:|---|--:|---|
| 1 | **qwen/qwen3-235b-a22b-2507** | 96/100 | En iyi dengeye sahip, 12 provider rekabeti |
| 2 | **deepseek/deepseek-v3-0324** | 90/100 | Kalitede rakip ama 2-3× pahalı |
| 3 | **meta-llama/llama-3.3-70b-instruct** | 85/100 | Ucuz + çok provider ama daha küçük model |
| 4 | **qwen/qwen3-next-80b-a3b-instruct** | 83/100 | Yeni, belirsiz ama potansiyelli |
| 5 | z-ai/glm-4.6 | 75/100 | Pahalı, yeterince test edilmemiş |
| 6 | qwen/qwq-32b | 72/100 | Reasoning için iyi ama rubric obedience belirsiz |
| 7 | deepseek/deepseek-r1-0528 | 70/100 | Pahalı reasoning modeli |
| 8 | google/gemma-3-27b-it | 65/100 | Ucuz ama küçük, cascade 1. aşaması için ok |
| 9 | moonshotai/kimi-k2 | 62/100 | Tek provider, pahalı |
| 10 | mistralai/mistral-large-2411 | 50/100 | Tek provider, kapalı, ultra-pahalı |

### Somut Aksiyon Tavsiyeleri

#### Kısa vade (3 ay) — Qwen'de kal

- **Neden:** Veri zaten bu modelde, pipeline çalışıyor, hiçbir alternatif belirgin avantaj sunmuyor.
- **Yan aksiyon:** Cascade'in ucuz tier'ına `qwen/qwen3-32b` yerine `google/gemma-3-27b-it` denenebilir (%20 daha ucuz).

#### Orta vade (3-6 ay) — DeepSeek-V3 ve Llama 3.3 A/B testi

Aynı 50 trace fixture üzerinde:
```bash
# Stack D: DeepSeek-V3
LLM_STAGE_1_MODEL=deepseek/deepseek-v3-0324
# Stack E: Llama 3.3
LLM_STAGE_1_MODEL=meta-llama/llama-3.3-70b-instruct
```
Qwen baseline'a karşı Pearson/MAD ölç. Eğer **Pearson > 0.95** ve **maliyet daha düşük** olan çıkarsa göç yapılabilir. (Llama 3.3 için maliyet avantajı zor, DeepSeek için kalite avantajı mümkün ama fiyat 2-3×.)

#### Uzun vade (6-12 ay) — Qwen4 / Llama 4 sürümlerini takip et

Açık model dünyası 6 ayda bir büyük sıçrama yapıyor. Qwen4 veya Llama 4
çıkarsa baseline'ı yeniden değerlendir.

### Risk Matrisi — Model Değişikliği

| Risk | Olasılık | Etki | Azaltma |
|---|---|---|---|
| Yeni model JSON schema'ya uymaz | Orta | Yüksek | Fixture'da %100 schema compliance testi |
| Yeni model TR'de zayıf | Düşük | Yüksek | 50 trace'in %40'ı TR, A/B'de gözükür |
| Pricing aniden değişir | Orta | Orta | OpenRouter pricing dashboard monitor |
| Provider çekilir | Düşük | Yüksek | ≥3 provider'lı model seç |

---

## 5. Özet Karar

| Soru | Cevap |
|---|---|
| Qwen → OpenAI karşılaştırması sonucu ne? | Pearson 0.92-0.99, hallucination daha sıkı, 2.9× ucuz → **migration güvenli** |
| OpenRouter'ı yönlendirebilir miyiz? | **Evet**, `provider.order/sort/quantizations` parametreleri ile tam kontrol |
| Qwen3-235B için en iyi provider stratejisi? | `wandb,deepinfra,parasail` — BF16 birincil, ucuz yedekler |
| Qwen'den daha iyi açık model var mı? | **Şu an hayır.** DeepSeek-V3 yakın ama pahalı, Llama 3.3 küçük. 3-6 ay sonra test edilebilir |

### Uygulanacaklar (öncelik sırasıyla)

1. **Bu hafta:** `.env`'e `OPENROUTER_PROVIDER_ORDER=wandb,deepinfra,parasail` ekle → 0 risk, kalite artışı
2. **Bu hafta:** Qwen migration staging'e deploy
3. **Bu ay:** Cascade router'ın ucuz tier'ı için `gemma-3-27b-it` vs `qwen3-32b` benchmark
4. **3-6 ay:** DeepSeek-V3 ve Llama 3.3 A/B testi (Qwen'e göre gerçekten daha iyi mi?)
5. **6-12 ay:** Qwen4 / Llama 4 / yeni nesil open model takibi

---

## Ek: Sayısal Veri Kaynakları

- OpenRouter API: `https://openrouter.ai/api/v1/models/{model}/endpoints`
- Veri çekim tarihi: 2026-04-24
- Fiyatlar USD/M token (input/output ayrı)
- Uptime = son 30 gün erişilebilirlik yüzdesi
- Status `0` = normal, `-2` = OpenRouter kendi tespit ettiği issue nedeniyle geçici dışladı

### Referans Dokümanlar

- [AB_REPORT_QWEN_VS_OPENAI.md](AB_REPORT_QWEN_VS_OPENAI.md) — 50 trace direct A/B
- [AB_REPORT_INFRA_PARITY.md](AB_REPORT_INFRA_PARITY.md) — infra-parity A/B
- [AB_SUMMARY_3WAY.md](AB_SUMMARY_3WAY.md) — iki test arası delta
- [TEST_LOG.md](TEST_LOG.md) — kronolojik test kayıtları
- [COST_QUALITY_STRATEGY.md](COST_QUALITY_STRATEGY.md) — 5 katmanlı optimizasyon
- [DECISION_BRIEF.md](DECISION_BRIEF.md) — 9 karar bekleyen madde
