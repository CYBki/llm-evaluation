# Kalite-Öncelikli Maliyet Optimizasyon Stratejisi

> **"Kalite eşiğinin altına düşmeden, mümkün olan en az parayla aynı iş."**

Bu doküman, Qwen migration'ı sonrası maliyeti daha da düşürmek için
sıralı bir süreç tasarlar. Her optimizasyon katmanı bağımsızdır ve
birikimlidir; her biri uygulanmadan önce bir önceki faz ile kalite
dengesi doğrulanır.

## İçindekiler

1. [Ana Felsefe](#ana-felsefe)
2. [Şu Anki Baseline](#şu-anki-baseline)
3. [Neden Qwen — Alternatifler Matrisi](#neden-qwen--alternatifler-matrisi)
4. [5 Katmanlı Optimizasyon](#5-katmanlı-optimizasyon)
5. [Kalite Koruma Mekanizması](#kalite-koruma-mekanizması)
6. [Uygulama Yol Haritası](#uygulama-yol-haritası)
7. [Risk Matrisi](#risk-matrisi)
8. [İlk Somut Adım](#i̇lk-somut-adım)

---

## Ana Felsefe

**Lexicographic optimization:** kaliteyi kısıt olarak sabitle, maliyeti
objektif olarak minimize et.

```
min  cost(pipeline)
s.t. quality(pipeline) ≥ quality_threshold
```

"Biraz daha kaliteli olsun" diye para harcama; kalite eşiğini
geçiyorsa dur. "Biraz daha ucuz olsun" diye kaliteden kıyma; eşiği
korumalısın.

**Kalite eşiği (geçici, production verisiyle kalibre edilecek):**
- `overall_score` Pearson (vs current baseline) ≥ **0.90**
- `hallucination_score` agreement rate ≥ **%85**
- `faithfulness` MAD ≤ **0.08**

Bu eşikleri 1 aylık baseline izlemeden sonra kesinleştir.

---

## Şu Anki Baseline

| Değişken | Değer |
|---|---|
| Stage 1 modeli | `qwen/qwen3-235b-a22b-2507` |
| Stage 2 modeli | `qwen/qwen3-32b` |
| RAG metric modeli | `qwen/qwen3-32b` |
| Provider | OpenRouter otomatik (price-ascending) |
| Quantization | FP8 (çoğu provider) |
| Prompt caching | Aktif değil |
| Cascade routing | Aktif değil |
| Maliyet / trace | **~$0.0005** |
| Yıllık (10k/gün) | **~$1,825** |
| GPT-5.2 baseline | **~$21,000/yıl** (11.5× pahalı) |
| overall_score Pearson (vs GPT) | 0.923–0.993 |

GPT'den zaten 10–11× ucuz konumdayız. Bu dokümanın hedefi: **buradan 5×
daha ucuz** (GPT'ye göre ~50×) inmek, kaliteyi kaybetmeden.

---

## Neden Qwen — Alternatifler Matrisi

Qwen seçimimizin arka planı ve atlanan alternatifler:

| Model | Çıkış $/M | Kalite | Seçim sebebi veya atlama sebebi |
|---|--:|---|---|
| **qwen/qwen3-235b-a22b-2507** ✅ | $0.10 | ⭐⭐⭐⭐⭐ | MoE 235B (A22B active), JSON schema güçlü, 12 provider rekabeti → fiyat düşük |
| deepseek-v3.2 | $0.12 | ⭐⭐⭐⭐⭐ | Qwen ile benzer kalite, Çin menşeli → politika riski, benzer fiyat |
| meta-llama/llama-3.3-70b-instruct | $0.07 | ⭐⭐⭐⭐ | Qwen'den küçük, judge için yeterli olabilir ama Qwen ile değil Türkçe'de olabilir zayıf |
| mistralai/mistral-large-2411 | $0.30 | ⭐⭐⭐⭐ | EU menşeli avantaj var ama 3× pahalı |
| google/gemini-2.5-flash | $0.10 | ⭐⭐⭐⭐ | Kapalı model, vendor lock-in, rate limit sert |
| anthropic/claude-3.5-haiku | $0.50 | ⭐⭐⭐⭐⭐ | En kaliteli ama 5× pahalı |
| moonshotai/kimi-k2 | $0.08 | ⭐⭐⭐⭐ | 2M context avantajı; judge'a gerek yok, kalite henüz az doğrulanmış |
| cohere/command-r-plus | $0.15 | ⭐⭐⭐⭐ | RAG odaklı ama pahalı ve 12 provider yok |

**Qwen'in stratejik avantajı:** açık ağırlık → 12 farklı provider rekabet
ediyor → fiyat baskısı var → uzun vadede daha da düşecek. Vendor
lock-in yok.

**Potansiyel geçişler:** Llama 3.3 70B + DeepInfra **%30 daha ucuz**
olabilir. Bir sonraki benchmark fırsatında test edilmeli.

---

## 5 Katmanlı Optimizasyon

Katmanları **sırayla** uygula. Her katman bir öncekinin üzerine tasarruf
ekler.

### Katman 1 — Provider Seçimi

**Ne:** OpenRouter'a hangi provider'ı tercih ettiğimizi söyle.

**Neden:** OpenRouter default'ta price-ascending sıralıyor ama en ucuz
(DeepInfra) FP8 quantize + %95.89 uptime. Bir adım daha pahalı olan
WandB BF16 quantize + %99.84 uptime ve **aynı output fiyatı**.

**Nasıl:** `.env`'e ekle:
```bash
OPENROUTER_PROVIDER_ORDER=wandb,deepinfra,parasail
```

**Beklenen:**
- Maliyet: %0 değişim (WandB ve DeepInfra output fiyatı aynı)
- Kalite: BF16 → skorlar hafif daha istikrarlı, non-determinism azalır
- Uptime: 95.89% → 99.84% (ayda ~28 saat daha az down)

**Risk:** Yok. Rollback tek satır silmek.

**Test:** 10 trace × iki config smoke, MAD < 0.02 olmalı.

---

### Katman 2 — Model Cascade (En Büyük Kazanç)

**Ne:** Kolay trace'ler için küçük/ucuz model, zor olanlar için büyük
model. "Routing" veya "cascading evaluator" pattern.

**Neden:** Bütün trace'ler 235B modele ihtiyaç duymaz. "Paris is the
capital of France" → apaçık doğru → 32B yeter. "OSes in Linux kernel
versioning use semantic versioning for backward compatibility" gibi
nüanslı iddialar → 235B gerekli.

**Nasıl:**

```python
# app/evaluation/cascade.py (yeni modül)
async def evaluate_with_cascade(trace):
    # Aşama A: Hızlı ön-değerlendirme
    stage_a = await judge(trace, model="qwen/qwen3-32b")
    # ~$0.00005, 3s, düşük context

    # Confidence metrikleri:
    # - logprobs (provider destekliyorsa)
    # - skor uç değer mi? (>0.9 veya <0.1 genelde güvenli)
    # - rubric'te "uncertain" flag'i var mı?
    if stage_a.confidence > 0.85:
        return stage_a

    # Aşama B: Detaylı değerlendirme
    return await judge(trace, model="qwen/qwen3-235b-a22b-2507")
```

**Trafik dağılımı tahmini:**

| Trace tipi | Oran | Hangi model yeter |
|---|--:|---|
| Obvious pass (faithful, kısa) | 40% | qwen3-32b ✅ |
| Obvious fail (major hallucination) | 15% | qwen3-32b ✅ |
| Orta zorluk (subtle, partial) | 35% | qwen3-235b gerekli |
| Edge case (off-topic, deflection) | 10% | qwen3-235b gerekli |

**Maliyet matematiği:**
```
Mevcut: 100% × $0.0005 = $0.0005/trace
Cascade: 55% × $0.00005 + 45% × $0.0005 = $0.000253/trace
Tasarruf: %49
```

**Kalite garantisi:**
- Random %5 trace her iki model ile paralel değerlendirilir (shadow)
- MAD > 0.08 olursa alarm, cascade_threshold yükseltilir
- cascade_threshold config'ten yönetilebilir

**Risk:** Orta. Cascade router yanlış kararla kalite düşürebilir → %5
shadow test zorunlu.

---

### Katman 3 — Prompt Caching

**Ne:** Her trace'de değişmeyen kısmı (system prompt + rubric) provider
cache'inde tut.

**Neden:** Prompt yapımız:

```
┌─────────────────────────────────────┐
│ System prompt + rubric  (3500 tok) │ ← HER TRACE AYNI
├─────────────────────────────────────┤
│ JSON schema + examples   (500 tok) │ ← HER TRACE AYNI
├─────────────────────────────────────┤
│ Trace-specific Q/A/ctx   (~800 tok)│ ← Her trace farklı
└─────────────────────────────────────┘
```

Her trace 4800 token gönderiyoruz, 4000'i aynı. Cache'lersek %90
indirim.

**Nasıl:** OpenRouter payload'una ekle:

```python
messages = [
    {
        "role": "system",
        "content": system_prompt,
        "cache_control": {"type": "ephemeral"}  # OpenRouter/Anthropic-style
    },
    {"role": "user", "content": trace_specific_content}
]
```

Provider desteği:
- Anthropic: evet (native)
- DeepInfra, WandB: evet (2025 Q4'ten beri)
- Parasail: kısmi

**Beklenen tasarruf:** input token maliyetinin %90'ı. Input/output
oranımız 3:1 olduğundan toplam maliyetin ~%25'i.

**Risk:** Çok düşük. Cache miss durumunda otomatik full pricing.

---

### Katman 4 — Semantic Deduplication

**Ne:** Aynı veya benzer trace'ler için cache'ten dön.

**Neden:** Production'da aynı chatbot cevabının çok kullanıcı tarafından
tekrar tekrar değerlendirilmesi olağan. %10-20 gerçek duplicate var.

**Nasıl:**

```python
async def evaluate_cached(trace):
    # Exact hash
    fp = sha256(canonicalize(trace))
    if fp in exact_cache:
        return exact_cache[fp]

    # Semantic
    emb = await embed(trace.canonical_text)
    hits = vector_cache.search(emb, threshold=0.95)
    if hits:
        return adapt_result(hits[0].result, trace)

    result = await evaluate_with_cascade(trace)
    cache_it(fp, emb, result)
    return result
```

**Storage:** PostgreSQL `pgvector` extension veya Redis + vector add-on.
Zaten Postgres'imiz var, `pgvector` ekstensiyonu eklemek yeterli.

**Beklenen tasarruf:** %10-20.

**Risk:** Orta. Cache invalidation:
- Rubric değişirse tüm cache bayat → TTL 30 gün
- Model değişirse cache namespace'i değiştir

---

### Katman 5 — Distillation (Uzun Vade)

**Ne:** Qwen3-235B çıktılarıyla küçük bir modeli (Qwen2.5-7B veya
Llama3-8B) fine-tune et, self-host et veya ucuz provider'da kullan.

**Neden:** 7B modelin maliyeti 235B'nin ~%3'ü. Kalite benchmark yapılmış
distillation'da %97-99 uyum elde ediliyor.

**Nasıl (fazlar):**

1. **Veri toplama (3 ay):** Production'da Qwen3-235B çıktılarını logla.
   ~1M input/output çifti hedef.
2. **Training (1 hafta):** LoRA veya full fine-tune. Tahmini GPU
   maliyeti: $500-2000 (8×H100, 24-72 saat).
3. **Evaluation (2 hafta):** Sentinel set + shadow run.
4. **Production cutover (1 ay):** %1 → %10 → %50 → %100 kademeli.

**Beklenen:** $0.000253 → $0.00003 / trace.

**Risk:** Yüksek. Altyapı yatırımı + kalite drift izleme + yeniden
eğitim cycle'ı.

**Alternatif:** Önceden distilled açık-kaynak modeller kullan (ör.
`Qwen2.5-7B-Instruct-distilled-from-Qwen3-235B` — böyle bir model
topluluktan gelirse ücretsiz alternatif).

---

## Kalite Koruma Mekanizması

Her optimizasyonla birlikte bu mekanizmalar aktif olmalı:

### 1. Continuous Shadow A/B

```
%5 production trafiği her zaman:
  - Primary pipeline (optimize)
  - Full baseline (qwen3-235b no cache no cascade)
  paralel değerlendirilir.

Haftalık metrik:
  - Pearson(primary, baseline)
  - MAD per metric
  - agreement_rate on hallucination/faithful flags

Alarm eşiği:
  - overall_score Pearson < 0.90 → sayfala
  - MAD > 0.08 → uyarı + otomatik rollback tetiklenebilir
```

### 2. Ground-Truth Sentinel Set

30-50 insan-etiketli altın trace. Her konfig değişiminde bunlara karşı
accuracy ölçülür. Eşik altı değişiklikler reddedilir (CI gate).

### 3. Drift Detection

Haftalık skor dağılımı izleme. Ortalama overall_score bir hafta içinde
>0.05 değişirse → model veya upstream değişmiş olabilir, investiga.

### 4. Fallback Always-On

Her optimizasyon katmanının bir "bypass" bayrağı vardır:
```bash
CASCADE_DISABLED=true
PROMPT_CACHE_DISABLED=true
SEMANTIC_CACHE_DISABLED=true
```

Herhangi bir optimizasyon sorun çıkarırsa tek env ile devre dışı.

---

## Uygulama Yol Haritası

| Faz | Süre | Eylem | Kazanç | Risk |
|---|---|---|---|---|
| 1 | 1 gün | Provider pin | %0 cost, +kalite | Yok |
| 2 | 1-2 hafta | Cascade + sentinel set | %40-50 ↓ | Düşük |
| 3 | 1 hafta | Prompt caching | %20-30 ↓ | Çok düşük |
| 4 | 2-4 hafta | Semantic dedup | %10-20 ↓ | Orta |
| 5 | 3-6 ay | Distillation | %80 ↓ | Yüksek |

### Birikimli Maliyet Projeksiyonu

| Durum | $/trace | Yıllık (10k/gün) | GPT'ye göre |
|---|--:|--:|--:|
| GPT-5.2 baseline | $0.2885 | $21,060 | 1× |
| Qwen (şu an) | $0.00050 | $1,825 | 11.5× ucuz |
| Faz 1-3 sonu | $0.00018 | $657 | 32× ucuz |
| Faz 4 sonu | $0.00015 | $548 | 38× ucuz |
| Faz 5 sonu | $0.00003 | $110 | **190× ucuz** |

---

## Risk Matrisi

| Risk | Olasılık | Etki | Azaltma |
|---|---|---|---|
| Cascade küçük modeli yanlış değerlendirir | Orta | Yüksek | %5 shadow, drift alarm, threshold tunable |
| Prompt cache bayatlar | Düşük | Orta | TTL + rubric version key |
| Semantic cache yanlış eşleşme | Orta | Orta | threshold 0.95+, embedding quality test |
| Distillation kalite kaybı | Yüksek | Çok yüksek | Sentinel gate + kademeli rollout |
| OpenRouter provider çöker | Orta | Yüksek | fallback chain `wandb → deepinfra → parasail` |
| Qwen ailesi breaking change | Düşük | Yüksek | Model version pinning + semver check |
| Kalite metrikleri konsepti değişir | Düşük | Yüksek | Sentinel set versiyonla, metrik migrasyon playbook |

---

## İlk Somut Adım

**Faz 2 (cascade router)** en yüksek ROI:

- Kod değişikliği minimal: ~100 satır yeni modül
- Beklenen kazanç: %50 maliyet düşüşü (yıllık $900+ tasarruf)
- A/B altyapısı hazır (üç stack var)
- Risk düşük (her zaman bypass edilebilir)

### İlk iterasyon pseudo-code

```python
# app/evaluation/cascade.py
from app.evaluation.judge import evaluate as full_judge
from app.evaluation.llm_client import chat_complete

CHEAP_MODEL = "qwen/qwen3-32b"
EXPENSIVE_MODEL = "qwen/qwen3-235b-a22b-2507"
CONFIDENCE_THRESHOLD = 0.85  # tunable, start conservative


async def cascade_evaluate(trace: Trace) -> Evaluation:
    """Two-stage evaluation: cheap model first, expensive only if needed."""
    # Stage A: quick judge with same rubric but cheap model
    stage_a = await full_judge(trace, model=CHEAP_MODEL, mode="quick")

    if stage_a.confidence >= CONFIDENCE_THRESHOLD:
        stage_a.metadata["cascade_tier"] = "cheap"
        return stage_a

    # Stage B: full judge
    stage_b = await full_judge(trace, model=EXPENSIVE_MODEL, mode="full")
    stage_b.metadata["cascade_tier"] = "expensive"
    stage_b.metadata["stage_a_score"] = stage_a.overall_score
    return stage_b
```

### Değişiklik gereken yerler

1. `app/evaluation/cascade.py` — yeni modül
2. `app/evaluation/judge.py` — `confidence` alanı rubric'e eklenir
3. `app/schemas/evaluation.py` — rubric output schema'sına `confidence: float`
4. `app/config.py` — `CASCADE_ENABLED`, `CASCADE_THRESHOLD` env değişkenleri
5. `app/tasks/evaluate.py` — cascade_enabled ise `cascade_evaluate`, değilse mevcut path
6. `tests/test_cascade.py` — unit + integration
7. 50-trace A/B: mevcut vs cascade; Pearson/MAD raporu

### Başarı kriteri (PR merge için)

- `overall_score` Pearson(cascade, baseline) ≥ 0.95
- `hallucination_score` agreement rate ≥ %90
- 50 trace'te ortalama maliyet en az %30 düşmüş
- Tüm mevcut testler yeşil
- `CASCADE_ENABLED=false` ile davranış birebir önceki hâl

---

## Sonuç

Qwen migration **başlangıç noktası**, son hedef değil. Bu dokümanla:

- GPT'ye göre 10× avantajı **190×**'e çıkarabiliriz (5 fazda)
- Her adım izole → yanlış gidince tek env ile rollback
- Kalite asla sabit eşiğin altına düşmez
- Her adımın test ve izleme mekanizması planlı

Sırası geldiğinde Faz 2 ile başlarız.
