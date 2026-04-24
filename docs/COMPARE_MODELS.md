# A/B Karşılaştırma: Qwen (OpenRouter) vs OpenAI

Aynı trace'leri iki bağımsız stack'e gönderip skorları yan yana karşılaştırmak için.

## Mimari

```
┌────────────────────────┐         ┌────────────────────────┐
│  Qwen stack            │         │  OpenAI stack          │
│  docker-compose.yml    │         │  docker-compose.openai │
│  .env                  │         │  .env.openai           │
│  port 8000             │         │  port 8001             │
│  LLM → OpenRouter      │         │  LLM → OpenAI          │
│  pgdata (vol)          │         │  pgdata (vol)          │
└────────────────────────┘         └────────────────────────┘
            ▲                                 ▲
            │                                 │
            └──── scripts/compare_models.py ──┘
                     (aynı trace'i ikisine yollar,
                      skorları karşılaştırır)
```

Aynı kodbase, iki farklı env ve iki farklı Docker project'i ile çalışır. Container/DB izolasyonu Docker project name (`-p`) sayesinde sağlanır.

## 1. OpenAI stack'ini ayağa kaldır

```bash
# Şablonu kopyala ve gerçek OpenAI key'ini gir
cp .env.openai.example .env.openai
# .env.openai'i düzenle: LLM_API_KEY=sk-...

# Paralel stack'i başlat (farklı project name + port)
docker compose -f docker-compose.openai.yml \
  -p llm-eval-openai \
  --env-file .env.openai \
  up -d --build
```

Doğrulama:

```bash
docker compose -f docker-compose.openai.yml -p llm-eval-openai ps
curl http://localhost:8001/health  # veya ingest endpoint'i
```

## 2. Her iki stack'te de bir kullanıcı oluştur ve API key al

Her stack'in kendi DB'si olduğundan auth kayıtları ayrıdır. Register + login akışını **her iki** endpoint'te ayrı ayrı çalıştır:

```bash
# Qwen stack (port 8000)
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@example.com","password":"secret123"}'

# OpenAI stack (port 8001) — aynı komutu 8001'de tekrarla
curl -X POST http://localhost:8001/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@example.com","password":"secret123"}'
```

Register response'unda (veya ayrı bir "API key oluştur" endpoint'i varsa oradan) dönen API key'leri not al.

## 3. Trace listesini hazırla

`traces.json`:

```json
[
  {
    "question": "Python'da GIL nedir ve hangi sürümde opsiyonel oldu?",
    "answer": "GIL ... Python 3.12'den itibaren ...",
    "contexts": ["PEP 703 ... Python 3.13 ..."],
    "ground_truth": "Python 3.13 / PEP 703",
    "metadata": {"tag": "gil"}
  },
  { "question": "...", "answer": "...", "contexts": ["..."] }
]
```

En az 10-20 trace ile anlamlı istatistik çıkar.

## 4. Karşılaştırmayı çalıştır

```bash
python scripts/compare_models.py \
  --traces traces.json \
  --qwen-url http://localhost:8000   --qwen-key <qwen_api_key> \
  --openai-url http://localhost:8001 --openai-key <openai_api_key> \
  --out compare_raw.json
```

Çıktı:

- **Per-trace tablo** — her metriğin Qwen ve OpenAI skoru yan yana
- **Aggregate stats** — her metrik için: ortalama, mean diff, MAD, Pearson korelasyonu
- **Totals** — toplam maliyet, token, ortalama süre

## 5. Yorumlama — Eşikler

| İstatistik | Hedef | Yorum |
|---|---|---|
| Pearson (r) | ≥ 0.85 | İki model sıralamada uyumlu |
| Mean diff | \|μ\| < 0.05 | Systematic bias yok |
| MAD | < 0.1 | Örnek bazında tutarlı |
| Hallucination `claim count` agreement | Cohen's κ ≥ 0.75 (elle) | Claim etiketleri tutarlı |

Tutmazsa:
- Sistematik bias varsa → Qwen prompt'unu minik ayarlayabilir veya scoring penalty'sini yeniden kalibre edebilirsin.
- Düşük korelasyon tek bir metrikteyse → o metriğin prompt'u probleme neden olabilir; sadece onu inceleyip iyileştir.

## 6. Temizlik

```bash
# OpenAI stack'ini kaldır (volume dahil tamamen silmek için -v)
docker compose -f docker-compose.openai.yml -p llm-eval-openai down -v
```

Qwen stack bağımsız, ona dokunulmaz.
