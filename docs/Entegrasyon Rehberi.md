# RAG Eval Tool — Entegrasyon Rehberi

> RAG ve Agent sistemlerinin cevap kalitesini **otomatik** olarak ölçen değerlendirme platformu.
>
> Bu rehber, tool'u kendi projenize nasıl entegre edeceğinizi adım adım anlatır.

---

## İçindekiler

1. [Bu Tool Ne Yapar?](#1-bu-tool-ne-yapar)
2. [Başlamadan Önce (2 Dakika)](#2-başlamadan-önce-bir-kez-yapılır-2-dakika)
3. [RAG Projesi Entegrasyonu](#3-rag-projesi-entegrasyonu)
4. [Agent Projesi Entegrasyonu](#4-agent-projesi-entegrasyonu)
5. [Sonuçları Görüntüleme](#5-sonuçları-görüntüleme)
6. [Metrikler ve Verdictler](#6-metrikler-ve-verdictler)
7. [Multi-Agent Değerlendirme Detayları](#7-multi-agent-değerlendirme-detayları)
8. [API Referansı](#8-api-referansı)
9. [SSS](#9-sss)

---

## 1. Bu Tool Ne Yapar?

Siz RAG veya Agent sisteminizi normal kullanırsınız. Tool arka planda şunları yapar:

```
Kullanıcı soru sorar
        │
        ▼
RAG/Agent sisteminiz cevap üretir
        │
        ▼
Tool otomatik olarak soru + cevap + context'leri yakalar
        │
        ▼
LLM-as-Judge ile 9 metrikle değerlendirir
        │
        ▼
Sonuçlar DB'ye kaydedilir, API'den okunabilir
```

**Değerlendirilen 9 metrik:**

| Metrik | Ne Ölçer? |
|--------|-----------|
| hallucination_score | Cevap kaynaklara sadık mı, uydurma var mı? |
| answer_relevancy | Cevap soruyla ilgili mi? |
| context_precision | Getirilen context'ler soruyla ilgili mi? |
| context_recall | Gerekli bilgiler context'lerde var mı? |
| completeness | Cevap sorunun tüm yönlerini kapsıyor mu? |
| coherence | Cevap tutarlı ve mantıklı mı? |
| clarity | Cevap açık ve anlaşılır mı? |
| helpfulness | Cevap kullanıcıya faydalı mı? |
| citation_check | İddialar doğru kaynaklara referans veriyor mu? |

Her metrik 0.0–1.0 arasında bir skor alır ve otomatik olarak **good** / **warning** / **bad** verdict'i atanır.

---

## 2. Başlamadan Önce (Bir Kez Yapılır, 2 Dakika)

> **Not:** RAG Eval sunucusu sizin için zaten deploy edilmiş ve çalışıyor.
> Sizin Docker kurmanıza, sunucu ayağa kaldırmanıza veya herhangi bir altyapı işi yapmanıza **gerek yok**.
> Sadece aşağıdaki adımları takip edin.

### Adım 1: API Key Al

Tarayıcınızda `http://SUNUCU_IP:8000/docs` adresini açın. Bu adres zaten çalışan sunucunun Swagger UI arayüzüdür — herhangi bir tarayıcıdan direkt erişilebilir.

1. `POST /api/v1/auth/register` endpoint'ini bulun → **Try it out** butonuna tıklayın
2. E-posta ve şifre girin → **Execute** butonuna tıklayın
3. Response'daki `api_key` değerini kopyalayın

> ⚠️ **`api_key` sadece bir kez gösterilir.** Hemen kaydedin.

### Adım 2: Projenize .env Ekleyin

Projenizin kök dizinindeki `.env` dosyasına şu iki satırı ekleyin:

```env
RAGEVAL_API_URL=http://SUNUCU_IP:8000
RAGEVAL_API_KEY=re_VWV-beeZ5P7_... (Swagger'dan aldığınız key)
```

### Adım 3: httpx Yükleyin

Projenizin terminalinde:

```bash
pip install httpx
```

> `httpx` zaten çoğu LLM projesinde kuruludur. Yoksa tek komutla eklenir.

### Adım 4: Kodunuzda Okuyun

RAG veya Agent kodunuzun bulunduğu dosyanın **en üstüne** şunu ekleyin:

```python
import os
import httpx

RAGEVAL_API_URL = os.getenv("RAGEVAL_API_URL")
RAGEVAL_API_KEY = os.getenv("RAGEVAL_API_KEY")
```

**Bu kadar. Artık projeniz RAG Eval'e bağlanmaya hazır.** Şimdi Bölüm 3 (RAG) veya Bölüm 4'e (Agent) geçin.

---

## 3. RAG Projesi Entegrasyonu

RAG projenizde retriever context getirir, LLM cevap üretir. Tek yapmanız gereken: **cevap üretildikten sonra 3 satır eklemek.**

### 3.1 Mevcut RAG Kodunuz (değişmez)

```python
# Sizin mevcut kodunuz — AYNEN KALIR
question = "Türkiye'nin başkenti neresidir?"
docs = retriever.get_relevant_documents(question)
contexts = [doc.page_content for doc in docs]
answer = llm.invoke(prompt.format(context=contexts, question=question))
```

### 3.2 Eklemeniz Gereken Kod (3 satır)

```python
# ↓↓↓ Mevcut kodunuzun HEMEN ALTINA ekleyin ↓↓↓
import httpx

httpx.post(f"{RAGEVAL_API_URL}/api/v1/ingest",
    headers={"X-API-Key": RAGEVAL_API_KEY},
    json={"question": question, "answer": answer, "contexts": contexts}
)
```

**Bu kadar.** Bundan sonra her soru-cevap otomatik olarak değerlendirilir.

### 3.3 Tam Örnek (Öncesi → Sonrası)

**ÖNCE (değerlendirme yok):**

```python
import os
from langchain.vectorstores import FAISS
from langchain.chat_models import ChatOpenAI

retriever = FAISS.load_local("my_index", embeddings).as_retriever()
llm = ChatOpenAI(model="gpt-4")

def answer_question(question: str) -> str:
    docs = retriever.get_relevant_documents(question)
    contexts = [doc.page_content for doc in docs]
    answer = llm.invoke(f"Context: {contexts}\n\nSoru: {question}")
    return answer
```

**SONRA (otomatik değerlendirme eklenmiş):**

```python
import os
import httpx                                                          # ← YENİ
from langchain.vectorstores import FAISS
from langchain.chat_models import ChatOpenAI

RAGEVAL_API_URL = os.getenv("RAGEVAL_API_URL")                       # ← YENİ
RAGEVAL_API_KEY = os.getenv("RAGEVAL_API_KEY")                       # ← YENİ

retriever = FAISS.load_local("my_index", embeddings).as_retriever()
llm = ChatOpenAI(model="gpt-4")

def answer_question(question: str) -> str:
    docs = retriever.get_relevant_documents(question)
    contexts = [doc.page_content for doc in docs]
    answer = llm.invoke(f"Context: {contexts}\n\nSoru: {question}")

    # ────── RAG Eval entegrasyonu (3 satır) ──────
    httpx.post(f"{RAGEVAL_API_URL}/api/v1/ingest",                   # ← YENİ
        headers={"X-API-Key": RAGEVAL_API_KEY},                      # ← YENİ
        json={"question": question, "answer": answer, "contexts": contexts}  # ← YENİ
    )

    return answer
```

> 💡 `# ← YENİ` ile işaretlenen satırlar dışında hiçbir şey değişmedi.

### 3.4 Değerlendirme Bloke Etmesin İstiyorsanız (Opsiyonel)

Değerlendirme ~10-30 saniye sürebilir. Cevabı bekletmek istemiyorsanız arka planda gönderin:

```python
import threading

def _send_eval(question, answer, contexts):
    httpx.post(f"{RAGEVAL_API_URL}/api/v1/ingest",
        headers={"X-API-Key": RAGEVAL_API_KEY},
        json={"question": question, "answer": answer, "contexts": contexts}
    )

# Ana kodunuzda:
threading.Thread(target=_send_eval, args=(question, answer, contexts)).start()
```

---

## 4. Agent Projesi Entegrasyonu

Agent (LangChain AgentExecutor) kullanıyorsanız da aynı `httpx.post` yöntemi. Ekstra dosya kopyalamaya veya paket kurmaya **gerek yok**.

Tek fark: `return_intermediate_steps=True` ekleyip adımları da göndermeniz.

### 4.1 Mevcut Agent Kodunuz (değişmez)

```python
from langchain.agents import AgentExecutor, create_tool_calling_agent

agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools)
result = executor.invoke({"input": "soru"})
```

### 4.2 Eklemeniz Gereken Kod (5 satır)

```python
from langchain.agents import AgentExecutor, create_tool_calling_agent
import httpx                                                                    # ← YENİ

agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, return_intermediate_steps=True)  # ← YENİ

result = executor.invoke({"input": question})

# ────── Agent Eval entegrasyonu (5 satır) ──────
steps = [                                                                       # ← YENİ
    {"step_index": i+1, "agent": step[0].tool,                                 # ← YENİ
     "input": str(step[0].tool_input), "output": str(step[1])}                 # ← YENİ
    for i, step in enumerate(result["intermediate_steps"])                      # ← YENİ
]                                                                               # ← YENİ

httpx.post(f"{RAGEVAL_API_URL}/api/v1/ingest",                                 # ← YENİ
    headers={"X-API-Key": RAGEVAL_API_KEY},                                    # ← YENİ
    json={                                                                      # ← YENİ
        "question": question,                                                   # ← YENİ
        "answer": result["output"],                                            # ← YENİ
        "metadata": {"pipeline_type": "multi-agent", "steps": steps}           # ← YENİ
    }                                                                           # ← YENİ
)                                                                               # ← YENİ
```

**Bu kadar.** Hiçbir dosya kopyalamaya, ekstra kütüphane kurmaya gerek yok. RAG ile aynı pattern:
- `return_intermediate_steps=True` → LangChain zaten tüm adımları veriyor
- Adımları `steps` listesine çevirin
- `httpx.post` ile gönderin
- Her adım ayrı ayrı 9 metrikle değerlendirilir

### 4.3 Tam Örnek (Öncesi → Sonrası)

**ÖNCE (değerlendirme yok):**

```python
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import DynamicTool
from langchain.chat_models import ChatOpenAI

llm = ChatOpenAI(model="gpt-4")
agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools)

def ask_agent(question: str) -> str:
    result = executor.invoke({"input": question})
    return result["output"]
```

**SONRA (otomatik değerlendirme eklenmiş):**

```python
import os
import httpx                                                                    # ← YENİ
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import DynamicTool
from langchain.chat_models import ChatOpenAI

RAGEVAL_API_URL = os.getenv("RAGEVAL_API_URL")                                 # ← YENİ
RAGEVAL_API_KEY = os.getenv("RAGEVAL_API_KEY")                                 # ← YENİ

llm = ChatOpenAI(model="gpt-4")
agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, return_intermediate_steps=True)  # ← DEĞİŞTİ

def ask_agent(question: str) -> str:
    result = executor.invoke({"input": question})

    # ────── Agent Eval entegrasyonu ──────
    steps = [                                                                   # ← YENİ
        {"step_index": i+1, "agent": step[0].tool,                             # ← YENİ
         "input": str(step[0].tool_input), "output": str(step[1])}             # ← YENİ
        for i, step in enumerate(result["intermediate_steps"])                  # ← YENİ
    ]                                                                           # ← YENİ
    httpx.post(f"{RAGEVAL_API_URL}/api/v1/ingest",                             # ← YENİ
        headers={"X-API-Key": RAGEVAL_API_KEY},                                # ← YENİ
        json={"question": question, "answer": result["output"],                # ← YENİ
              "metadata": {"pipeline_type": "multi-agent", "steps": steps}}    # ← YENİ
    )                                                                           # ← YENİ

    return result["output"]
```

> 💡 Sadece `# ← YENİ` ve `# ← DEĞİŞTİ` satırları eklendi. Geri kalan kodunuz aynen duruyor.

### 4.4 Ne Zaman Ne Kullanılır?

| Proje Tipi | Ne Eklenir? | Ek Paket | Satır Sayısı |
|------------|-------------|----------|--------------|
| RAG (retriever → LLM) | `httpx.post(...)` | httpx | 3 satır |
| Agent (AgentExecutor) | `httpx.post(...)` + `return_intermediate_steps` | httpx | 5 satır |
| RAG + Agent karışık | İkisini birden ekleyin | httpx | — |

> Her iki durumda da aynı yöntem: sadece `httpx.post`. Ekstra dosya veya kütüphane gerekmez.

---

## 5. Sonuçları Görüntüleme

Değerlendirme sonuçlarını iki şekilde görebilirsiniz:

### 5.1 Swagger UI ile (en kolay — kod yazmaya gerek yok)

Tarayıcınızda `http://SUNUCU_IP:8000/docs` adresini açın.

1. Sağ üstteki **Authorize** butonuna tıklayın → API key'inizi girin
2. `GET /api/v1/traces` → **Try it out** → **Execute** → Tüm trace'lerinizi skorlarıyla görün
3. Bir trace'in `id`'sini kopyalayın → `GET /api/v1/traces/{id}` → detaylı sonucu görün

> 💡 Hızlıca "acaba skorlarım nasıl?" diye bakmak istiyorsanız Swagger UI yeterlidir.

### 5.2 Projenizde Sonuçları Kullanma (opsiyonel)

Eğer sonuçları kendi projenizde programatik olarak kullanmak istiyorsanız (örneğin düşük skorlu cevapları loglamak, kullanıcıya uyarı göstermek vb.), projenize bir helper fonksiyon ekleyebilirsiniz:

```python
# ── projenizin utils.py veya eval_helpers.py dosyasına ekleyin ──

def get_eval_results(page: int = 1, per_page: int = 20) -> list:
    """Son trace değerlendirme sonuçlarını getirir."""
    resp = httpx.get(f"{RAGEVAL_API_URL}/api/v1/traces",
        headers={"X-API-Key": RAGEVAL_API_KEY},
        params={"page": page, "per_page": per_page}
    )
    return resp.json()["items"]


def get_trace_detail(trace_id: str) -> dict:
    """Tek trace'in detaylı değerlendirmesini getirir."""
    resp = httpx.get(f"{RAGEVAL_API_URL}/api/v1/traces/{trace_id}",
        headers={"X-API-Key": RAGEVAL_API_KEY}
    )
    return resp.json()
```

Bu fonksiyonları projenizin herhangi bir yerinden çağırabilirsiniz:

```python
# ── projenizin herhangi bir dosyasında ──
from eval_helpers import get_eval_results, get_trace_detail

# Son 20 trace'in özetini al
for trace in get_eval_results():
    ev = trace["evaluation"]
    print(f"Soru: {trace['question'][:50]}...")
    print(f"  Skor: {ev['overall_score']}  ({ev['verdicts']['overall_score']})")

# Tek trace detayı
detail = get_trace_detail("8a0d86a6-b843-441e-9039-d803a05a0974")
ev = detail["evaluation"]
print("Skorlar:", ev["scores"])       # 9 metriğin skorları
print("Verdictler:", ev["verdicts"])   # good / warning / bad
print("Özet:", ev["reasoning_summary"])
```

### 5.3 Düşük Skorları Otomatik Loglama (opsiyonel)

Cevap kalitesi düşük olduğunda otomatik loglama yapmak istiyorsanız, ingest çağrısından dönen `trace_id`'yi kullanabilirsiniz:

```python
# ── RAG fonksiyonunuzdaki mevcut entegrasyon kodunu şöyle genişletin ──

def answer_question(question: str) -> str:
    docs = retriever.get_relevant_documents(question)
    contexts = [doc.page_content for doc in docs]
    answer = llm.invoke(f"Context: {contexts}\n\nSoru: {question}")

    # Eval gönder ve trace_id'yi al
    resp = httpx.post(f"{RAGEVAL_API_URL}/api/v1/ingest",
        headers={"X-API-Key": RAGEVAL_API_KEY},
        json={"question": question, "answer": answer, "contexts": contexts}
    )
    trace = resp.json()

    # Değerlendirme tamamlandıysa skoru kontrol et
    if trace.get("status") == "completed":
        score = trace["evaluation"]["overall_score"]
        if score < 0.5:
            logger.warning(f"Düşük kalite cevap! Skor: {score}, Soru: {question[:80]}")

    return answer
```

### 5.4 Multi-Agent Sonuçları

Agent trace gönderdiyseniz, sonuçlarda her adımın ayrı değerlendirmesi ve pipeline skoru görünür:

```python
detail = get_trace_detail(trace_id)
ev = detail["evaluation"]

# Pipeline genel skoru
print(f"Pipeline Skor: {ev['pipeline_score']}  ({ev['pipeline_verdict']})")
# → Pipeline Skor: 0.92  (good)

# Her adımın ayrı skoru
for step in ev["step_evaluations"]:
    print(f"  {step['agent_name']}: {step['overall_score']}  ({step['verdicts']['overall_score']})")
# → retriever_agent:  1.00  (good)
# → summarizer_agent: 0.79  (warning)  ← bu adımı iyileştirin
# → validator_agent:  0.94  (good)
```

### 5.5 Debug Modu

Bir cevabın neden düşük skor aldığını anlamak için detaylı analiz isteyebilirsiniz:

```python
# Swagger UI'da: GET /api/v1/traces/{id}?detail=full
# veya kodda:
resp = httpx.get(f"{RAGEVAL_API_URL}/api/v1/traces/{trace_id}",
    headers={"X-API-Key": RAGEVAL_API_KEY},
    params={"detail": "full"}
)
ev = resp.json()["evaluation"]

print(ev["reasoning_summary"])          # İnsan-okunabilir değerlendirme özeti
print(ev["details"]["hallucination_claims"])  # Hangi iddia hangi kaynakla eşleşiyor
print(ev["details"]["completeness_key_points"])  # Hangi key point eksik
print(ev["stage_1_reasoning"])           # LLM'in düşünce zinciri (debug)
```

---

## 6. Metrikler ve Verdictler

### 6.1 Metrikler Detaylı Açıklama

| Metrik | Skor | Ne Anlama Geliyor? | Düşükse Ne Yapmalı? |
|--------|------|--------------------|--------------------|
| **hallucination_score** | 0.0–1.0 | 1.0 = tamamen kaynaklara sadık, 0.0 = tamamen uydurma | Prompt'ta "sadece verilen context'e göre cevap ver" talimatını güçlendirin |
| **answer_relevancy** | 0.0–1.0 | 1.0 = soruyla tam ilgili, 0.0 = alakasız | Prompt'ta soruya odaklanma talimatını ekleyin |
| **context_precision** | 0.0–1.0 | 1.0 = tüm context'ler ilgili, 0.0 = hepsi gereksiz | Retriever'ın top-k değerini düşürün veya re-ranker ekleyin |
| **context_recall** | 0.0–1.0 | 1.0 = gereken tüm bilgi context'te var, 0.0 = hiçbiri yok | Knowledge base'i genişletin, chunk boyutunu ayarlayın |
| **completeness** | 0.0–1.0 | 1.0 = sorunun tüm yönleri kapsanmış, 0.0 = çok eksik | Prompt'ta "tüm yönlerini kapsayan detaylı cevap ver" ekleyin |
| **coherence** | 0.0–1.0 | 1.0 = mantıklı ve tutarlı, 0.0 = çelişkili | Model sıcaklığını düşürün, daha güçlü model kullanın |
| **clarity** | 0.0–1.0 | 1.0 = açık ve anlaşılır, 0.0 = karışık | Prompt'ta "net ve kısa cevap ver" ekleyin |
| **helpfulness** | 0.0–1.0 | 1.0 = pratik ve faydalı, 0.0 = işe yaramaz | Prompt'ta "kullanıcıya somut, uygulanabilir öneriler sun" ekleyin |
| **citation_check** | 0.0–1.0 | 1.0 = doğru kaynak referansları, 0.0 = yanlış | Prompt'ta kaynak belirtme formatı tanımlayın |

### 6.2 Boolean Bayraklar

| Bayrak | `true` ise ne olur? |
|--------|---------------------|
| **is_off_topic** | Cevap soruyla alakasız → overall_score otomatik olarak **≤ 0.20**'ye düşürülür |
| **is_deflection** | Cevap geçiştirme ("bilmiyorum" gibi) → overall_score otomatik olarak **≤ 0.20**'ye düşürülür |

### 6.3 Verdict Eşikleri

Her metrik skoru otomatik olarak bir verdict etiketi alır:

| Verdict | Renk | Skor Aralığı | Anlam |
|---------|------|--------------|-------|
| **good** | 🟢 Yeşil | ≥ 0.8 | Metrik iyi seviyede, müdahale gerekmez |
| **warning** | 🟡 Sarı | 0.5 – 0.8 | İyileştirme alanı var, gözden geçirin |
| **bad** | 🔴 Kırmızı | < 0.5 | Ciddi sorun, müdahale edin |
| **critical** | ⚫ Siyah | < 0.2 | Çok ciddi (sadece hallucination_score için) |
| **null** | ⚪ Gri | — | Hesaplanamadı (ör. context gönderilmediğinde context_precision null olur) |

### 6.4 Metrik Tanımlarını Programatik Alma

Tüm metrik tanımlarını, eşiklerini ve açıklamalarını API'den çekebilirsiniz:

```python
resp = httpx.get(f"{RAGEVAL_API_URL}/api/v1/metrics/definitions")
metrics = resp.json()

for m in metrics:
    print(f"{m['key']}: {m['description']}")
    for t in m["thresholds"]:
        print(f"  {t['level']}: {t['min']}-{t['max']} → {t['explanation']}")
```

> Bu endpoint'e API key gerekmez. Uygulama başlangıcında bir kez çekip cache'leyebilirsiniz.

---

## 7. Multi-Agent Değerlendirme Detayları

### 7.1 Pipeline Score Nasıl Hesaplanır?

```
pipeline_score = 50% × trace_level_overall + 50% × ortalama(step_overall'ları)
```

Örnek:
```
Trace overall: 0.93
Step 1 (retriever):   1.00
Step 2 (summarizer):  0.79
Step 3 (validator):   0.94
Avg steps: (1.00 + 0.79 + 0.94) / 3 = 0.91

Pipeline score = 0.50 × 0.93 + 0.50 × 0.91 = 0.92
```

### 7.2 Context Davranışı

- Bir step'e `contexts` gönderirseniz → hallucination, context_precision, context_recall hesaplanır
- Göndermezseniz → bu metrikler `null` döner, diğerleri (clarity, coherence vb.) yine hesaplanır
- **Önerimiz:** Sadece retriever adımlarına context gönderin, diğer adımlara (summarizer, validator) gerek yok

### 7.3 Agent Adımları Nasıl Çalışır?

`return_intermediate_steps=True` eklediğinizde LangChain, agent'ın her tool çağrısını `result["intermediate_steps"]` listesinde döner:

```python
result = executor.invoke({"input": "soru"})

# result["intermediate_steps"] şöyle bir liste:
# [
#   (AgentAction(tool="retriever_agent", tool_input="..."), "tool çıktısı"),
#   (AgentAction(tool="summarizer_agent", tool_input="..."), "tool çıktısı"),
#   (AgentAction(tool="validator_agent", tool_input="..."), "tool çıktısı"),
# ]
```

Biz bunu `steps` listesine çevirip API'ye gönderiyoruz. Her step ayrı ayrı 9 metrikle değerlendirilir.

---

## 8. API Referansı

### Endpoint Özet Tablosu

| Metot | Endpoint | Auth | Ne Yapar? |
|-------|----------|------|-----------|
| POST | `/api/v1/auth/register` | ❌ | Kayıt ol, API key al |
| POST | `/api/v1/auth/login` | ❌ | Giriş yap (key prefix hatırlat) |
| POST | `/api/v1/ingest` | ✅ | Tek trace gönder (otomatik değerlendirilir) |
| POST | `/api/v1/ingest/batch` | ✅ | Toplu trace gönder (max 100) |
| GET | `/api/v1/traces` | ✅ | Trace listesi (sayfalanmış) |
| GET | `/api/v1/traces/{id}` | ✅ | Trace detayı (summary) |
| GET | `/api/v1/traces/{id}?detail=full` | ✅ | Trace detayı (debug bilgileriyle) |
| GET | `/api/v1/metrics/definitions` | ❌ | Metrik tanımları ve threshold'lar |
| GET | `/health` | ❌ | Sistem sağlık kontrolü |

### Kimlik Doğrulama

Auth gerektiren tüm endpoint'lerde `X-API-Key` header'ı gönderin:

```
X-API-Key: re_VWV-beeZ5P7_wJHNnQTfYW5mfdnQoj4cttHHnbnBkZU
```

### Ingest Request Alanları

| Alan | Tip | Zorunlu | Açıklama |
|------|-----|---------|----------|
| `question` | string | ✅ | Kullanıcının sorusu (1–50.000 karakter) |
| `answer` | string | ✅ | Sistemin ürettiği cevap (1–100.000 karakter) |
| `contexts` | string[] | ❌ | Retriever'ın getirdiği context parçaları |
| `ground_truth` | string | ❌ | Beklenen doğru cevap (ileride kullanılacak) |
| `metadata` | object | ❌ | Ek bilgi. Multi-agent için `steps` dizisini buraya koyun |

### Trace Response Yapısı

```
trace
├── id                    (string)   Trace UUID
├── question              (string)   Soru
├── answer                (string)   Cevap
├── contexts              (string[]) Context'ler
├── metadata              (object)   Metadata
├── status                (string)   "completed" | "pending" | "failed"
├── created_at            (datetime) Oluşturulma zamanı
└── evaluation
    ├── overall_score      (float)    Genel kalite skoru
    ├── confidence         (float)    Değerlendirme güveni
    ├── scores             (object)   9 metriğin skorları
    ├── verdicts           (object)   9 metriğin verdictleri (good/warning/bad)
    ├── flags              (object)   is_off_topic, is_deflection
    ├── reasoning_summary  (string)   İnsan-okunabilir değerlendirme özeti
    ├── details            (object)   Detaylı analiz
    │   ├── hallucination_claims      Hangi iddia hangi kaynakla eşleşiyor
    │   └── completeness_key_points   Hangi key point kapsamda, hangisi eksik
    │
    │── (detail=full modunda ek alanlar)
    │   ├── specificity            Cevabın spesifiklik skoru
    │   ├── stage_1_reasoning      LLM düşünce zinciri
    │   ├── disagreement_claims    Çelişen iddialar
    │   ├── model_used             Kullanılan model
    │   ├── prompt_version         Prompt versiyonu
    │   └── rubric_version         Rubric versiyonu
    │
    └── (multi-agent trace'lerde ek alanlar)
        ├── pipeline_score         Pipeline genel skoru
        ├── pipeline_verdict       Pipeline verdict'i
        └── step_evaluations[]     Her agent adımının değerlendirmesi
            ├── step_index         Adım sırası
            ├── agent_name         Agent adı
            ├── overall_score      Adım genel skoru
            ├── scores             Adım metrik skorları
            ├── verdicts           Adım verdictleri
            ├── flags              Adım bayrakları
            ├── reasoning_summary  Adım değerlendirme özeti
            └── details            Adım detaylı analizi
```

### Rate Limiting

| Endpoint | Limit |
|----------|-------|
| `POST /api/v1/ingest` | 30/dakika |
| `POST /api/v1/ingest/batch` | 10/dakika |
| Diğer tüm endpoint'ler | 60/dakika |

Limit aşılırsa `429 Too Many Requests` döner. 1 dakika sonra sıfırlanır.

### Hata Kodları

#### `401 Unauthorized` — API Key Hatası

API key gönderilmedi, yanlış yazıldı veya süresi doldu.

```json
{"error": "Unauthorized", "detail": "Invalid or missing API key"}
```

**Kontrol edin:**
- Header'da `X-API-Key` var mı? (`Authorization` değil, `X-API-Key`)
- Key'in başı `re_` ile başlıyor mu?
- `.env` dosyasındaki key ile gönderdiğiniz key aynı mı? (kopyalarken boşluk/satır sonu kaçmış olabilir)

```python
# ✅ Doğru
headers={"X-API-Key": "re_VWV-beeZ5P7_wJHNnQTfYW5mfdnQoj4cttHHnbnBkZU"}

# ❌ Yanlış — header adı farklı
headers={"Authorization": "Bearer re_VWV-..."}

# ❌ Yanlış — key sonunda boşluk var
headers={"X-API-Key": "re_VWV-beeZ5P7_wJHNnQTfYW5mfdnQoj4cttHHnbnBkZU "}
```

---

#### `404 Not Found` — Trace Bulunamadı

İstenen trace ID veritabanında yok **veya** başka bir kullanıcıya ait.

```json
{"error": "NotFound", "detail": "Trace not found"}
```

**Kontrol edin:**
- Trace ID doğru mu? (UUID formatında olmalı: `8a0d86a6-b843-441e-9039-d803a05a0974`)
- Bu trace'i siz mi oluşturdunuz? Başka bir API key ile oluşturulan trace'lere erişemezsiniz.
- Trace'i zaten silmiş olabilir misiniz?

---

#### `409 Conflict` — E-posta Zaten Kayıtlı

Aynı e-posta ile ikinci kez kayıt olmaya çalışıyorsunuz.

```json
{"error": "Conflict", "detail": "Email already registered"}
```

**Çözüm:**
- Zaten kayıtlıysanız → `POST /api/v1/auth/login` ile giriş yapın (key prefix'inizi hatırlatır)
- API key'inizi kaybettiyseniz → farklı bir e-posta ile yeni kayıt oluşturun

---

#### `422 Unprocessable Entity` — Request Formatı Yanlış

Zorunlu alanlar eksik, tipler yanlış veya karakter limiti aşılmış.

```json
{
  "error": "ValidationError",
  "detail": [
    {"field": "question", "message": "field required"},
    {"field": "answer", "message": "field required"}
  ]
}
```

**Sık yapılan hatalar:**

```python
# ❌ question eksik
httpx.post(url, headers=h, json={"answer": "..."})

# ❌ contexts string, liste olmalı
httpx.post(url, headers=h, json={"question": "?", "answer": ".", "contexts": "tek string"})

# ✅ Doğru
httpx.post(url, headers=h, json={
    "question": "Soru?",
    "answer": "Cevap.",
    "contexts": ["context parça 1", "context parça 2"]   # liste
})
```

**Alan limitleri:**
- `question`: 1–50.000 karakter
- `answer`: 1–100.000 karakter
- `contexts`: her eleman max 100.000 karakter, max 100 eleman

---

#### `429 Too Many Requests` — Rate Limit

Çok fazla istek gönderdiniz.

```json
{"error": "RateLimited", "detail": "Rate limit exceeded. Retry after 60 seconds."}
```

**Limitler:**
- `POST /ingest`: 30 istek/dakika
- `POST /ingest/batch`: 10 istek/dakika
- Diğer endpoint'ler: 60 istek/dakika

**Çözüm:** 1 dakika bekleyin veya `ingest/batch` kullanarak tek istekte birden fazla trace gönderin.

---

#### `500 Internal Server Error` — Sunucu Hatası

Sunucu tarafında beklenmeyen bir hata oluştu. Sizin kodunuzla ilgili değil.

```json
{"error": "InternalError", "detail": "An unexpected error occurred", "request_id": "uuid-..."}
```

**Ne yapmalı:**
1. 5 saniye bekleyip tekrar deneyin
2. Sorun devam ediyorsa `request_id`'yi not edin ve bize bildirin
3. `GET /health` ile sunucunun ayakta olup olmadığını kontrol edin

### Sağlık Kontrolü

```python
resp = httpx.get(f"{RAGEVAL_API_URL}/health")
# {"status": "ok", "details": {"api": "ok", "database": "ok"}}
```

---

## 9. SSS

**S: Context göndermek zorunlu mu?**
C: Hayır. Ama gönderirseniz hallucination_score, context_precision, context_recall metrikleri anlamlı çalışır. Göndermezseniz bu metrikler `null` döner, diğer 6 metrik yine hesaplanır.

**S: Değerlendirme ne kadar sürer?**
C: Tek trace için ~10-30 saniye. Multi-agent trace'lerde her step için ek ~10-20 saniye. Cevabın kullanıcıya dönmesini bekletmek istemiyorsanız `threading.Thread` ile arka planda gönderin ([Bölüm 3.4'e bakın](#34-değerlendirme-bloke-etmesin-istiyorsanız-opsiyonel)).

**S: Multi-agent mı yoksa normal trace mi göndermeliyim?**
C: Pipeline'ınız tek adımsa (soru → retriever → LLM → cevap) normal gönderin. Birden fazla agent/tool zinciri varsa `return_intermediate_steps=True` ekleyip adımları da gönderin ([Bölüm 4'e bakın](#4-agent-projesi-entegrasyonu)).

**S: Trace'lerim başka kullanıcılar tarafından görülebilir mi?**
C: Hayır. Her kullanıcı sadece kendi trace'lerini görebilir.

**S: API key'imi kaybettim, ne yapmalıyım?**
C: Yeni bir e-posta ile tekrar kayıt olun.

**S: `detail=summary` ve `detail=full` arasındaki fark nedir?**
C: `summary` kullanıcı-dostu temiz çıktı verir. `full` ek olarak LLM'in düşünce zincirini, kullanılan modeli, prompt versiyonunu ve çelişki detaylarını içerir. Normal kullanımda `summary` yeterlidir.

**S: Bir agent step'e context göndermesem ne olur?**
C: O step için hallucination_score, context_precision, context_recall `null` döner. Diğer metrikler yine hesaplanır.

**S: Toplu trace göndermek istiyorum, nasıl yaparım?**
C: `POST /api/v1/ingest/batch` endpoint'ini kullanın. Tek istekte max 100 trace gönderebilirsiniz:

```python
httpx.post(f"{RAGEVAL_API_URL}/api/v1/ingest/batch",
    headers={"X-API-Key": RAGEVAL_API_KEY},
    json={"traces": [
        {"question": "Soru 1", "answer": "Cevap 1", "contexts": ["..."]},
        {"question": "Soru 2", "answer": "Cevap 2", "contexts": ["..."]},
    ]}
)
```

**S: Sonuçları UI'da mı göreceğiz?**
C: Şu an sonuçlar API üzerinden okunur (Bölüm 5'teki Python kodları ile). Swagger UI'dan da (`/docs`) deneyebilirsiniz. Dashboard planlanmaktadır.
