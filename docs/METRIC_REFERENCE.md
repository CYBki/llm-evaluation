# RAG Evaluation Tool — Metrik Referans Dokümanı

> **Versiyon:** 2.0  
> **Tarih:** 23 Şubat 2026  
> **Hedef Kitle:** Geliştiriciler + Müşteriler  
> **Amaç:** Her metriğin ne olduğu, nasıl hesaplandığı, arka planda hangi prompt ve LLM'in çalıştığı, formülü ve JSON çıktı yapısı — tek dokümanda.

---

## İçindekiler

1. [Pipeline Genel Akış](#1-pipeline-genel-akış)
2. [Metrik Özet Tablosu](#2-metrik-özet-tablosu)
3. [Rubrik Metrikleri (Stage 1 — Cevap Kalitesi)](#3-rubrik-metrikleri-stage-1--cevap-kalitesi)
   - 3.1 [clarity](#31-clarity-netlik)
   - 3.2 [specificity](#32-specificity-özgüllük)
   - 3.3 [coherence](#33-coherence-tutarlılık)
   - 3.4 [helpfulness](#34-helpfulness-yardımcılık)
4. [RAG Analitik Metrikleri (Paralel — Grounding & Kapsam)](#4-rag-analitik-metrikleri-paralel--grounding--kapsam)
   - 4.1 [answer_relevancy](#41-answer_relevancy-cevap-ilgililiği)
   - 4.2 [hallucination_score](#42-hallucination_score-halüsinasyon-skoru)
   - 4.3 [completeness](#43-completeness-tamlık)
   - 4.4 [citation_check](#44-citation_check-kaynak-atfı-doğruluğu)
   - 4.5 [context_precision](#45-context_precision-bağlam-hassasiyeti)
   - 4.6 [context_recall](#46-context_recall-bağlam-kapsamı)
5. [Bayraklar (Flags)](#5-bayraklar-flags)
   - 5.1 [is_off_topic](#51-is_off_topic)
   - 5.2 [is_deflection](#52-is_deflection)
6. [overall_score — Bileşik Skor](#6-overall_score--bileşik-skor)
7. [Ek Çıktılar](#7-ek-çıktılar)
8. [SSS (Sık Sorulan Sorular)](#8-sss-sık-sorulan-sorular)
9. [Kod Referans Haritası](#9-kod-referans-haritası)

---

## 1. Pipeline Genel Akış

Bir trace (soru + cevap + context'ler + opsiyonel ground_truth) sisteme gönderildiğinde şu süreç **eş zamanlı** olarak başlar:

```
Trace (question, answer, contexts, ground_truth?)
     │
     ├──► [DAL A] Stage 1: Rubrik Değerlendirme ──► Stage 2: JSON Çıkarma
     │       Model: gpt-5.2 (16384 token)             Model: gpt-5-mini (2048 token)
     │       Çıktı: CoT reasoning metni                Çıktı: Yapısal JSON skorlar
     │       → clarity, specificity, coherence,
     │         helpfulness, is_off_topic, is_deflection
     │
    ├──► [DAL B] RAG Analitik Metrikler (6 paralel LLM çağrısı)
     │       Model: gpt-5-mini (her biri)
     │       ├── answer_relevancy
     │       ├── hallucination_score (dedicated two-stage judge)
     │       ├── citation_check
     │       ├── completeness
     │       ├── context_precision
     │       └── context_recall
     │
     └──► overall_score = ağırlıklı ortalama (kod tarafında hesaplanır, LLM kullanmaz)
```

**Toplam LLM çağrısı:** 8 (Stage 1 + Stage 2 + 6 RAG metrik)  
**Eş zamanlılık:** Dal A ve Dal B paralel; Dal B içindeki 6 metrik de paralel.  
**Toplam süre:** ~tek API round-trip süresi (paralel çalıştığı için).

### Stage 1 → Stage 2 İlişkisi

Stage 1, **Chain-of-Thought (CoT)** formatında serbest metin reasoning üretir. Bu metin Stage 2'ye gönderilir ve Stage 2 bunu yapısal JSON'a dönüştürür. Stage 2 başarısız olursa **3 retry** yapılır; hepsi başarısız olursa **regex fallback** ile Stage 1 metninden skorlar çıkarılır.

---

## 2. Metrik Özet Tablosu

| # | Metrik | Tür | Aralık | Neyi Ölçer | Neye Bakar | LLM Çağrısı |
|---|--------|-----|--------|------------|------------|-------------|
| 1 | clarity | Rubrik | 0.0–1.0 | Cevabın anlaşılırlığı | Cevap | Stage 1 |
| 2 | specificity | Rubrik | 0.0–1.0 | Cevabın somutluğu | Cevap | Stage 1 |
| 3 | coherence | Rubrik | 0.0–1.0 | Cevabın iç tutarlılığı | Cevap | Stage 1 |
| 4 | helpfulness | Rubrik | 0.0–1.0 | Cevabın faydalılığı | Cevap + Soru | Stage 1 |
| 5 | answer_relevancy | Analitik | 0.0–1.0 | Cevap ifadelerinin soruyla ilgisi | Cevap + Soru | Ayrı LLM |
| 6 | hallucination_score | Analitik | 0.0–1.0 | Uydurma bilgi oranı (ters) | Cevap + Context | Ayrı LLM (2-stage) |
| 7 | completeness | Analitik | 0.0–1.0 | Sorunun ne kadarının karşılandığı | Soru + Cevap + Context | Ayrı LLM |
| 8 | citation_check | Analitik | 0.0–1.0 / null | Atıf doğruluğu | Cevap + Context | Ayrı LLM |
| 9 | context_precision | Analitik | 0.0–1.0 | Getirilen belge kalitesi | Soru + Context | Ayrı LLM |
| 10 | context_recall | Analitik | 0.0–1.0 | Gerekli bilginin context'te varlığı | Soru + Context + GT | Ayrı LLM |
| 11 | is_off_topic | Bayrak | true/false | Cevap konu dışı mı | Cevap + Soru | Stage 1 |
| 12 | is_deflection | Bayrak | true/false | Cevap kaçamak mı | Cevap | Stage 1 |
| 13 | overall_score | Bileşik | 0.0–1.0 | Genel kalite | Tüm metrikler | Yok |

---

## 3. Rubrik Metrikleri (Stage 1 — Cevap Kalitesi)

Bu metriklerin tamamı **tek bir LLM çağrısıyla** değerlendirilir. LLM'e bir rubrik (puan kılavuzu) verilir ve CoT reasoning yazması istenir.

### Arka Planda Çalışan System Prompt

```
You are an expert RAG answer quality evaluator.
Strictly follow the rubric below when scoring.
For each metric, write brief but clear reasoning.
Use the anchor values (1.0 / 0.7 / 0.4 / 0.0) as reference points when scoring.
Do NOT perform claim-level fact-checking — that is handled by a separate analytical pipeline.
Focus only on the rubric dimensions listed.
```

### LLM'e Gönderilen User Prompt Yapısı

```
[RUBRIC BLOCK — aşağıdaki rubrik skalası]

Question:
{kullanıcının sorusu}

Answer:
{sistemin cevabı}

Contexts:
- {context 1}
- {context 2}
- ...

For each rubric metric, write brief reasoning and propose a score.
```

### Kullanılan Rubrik (Puan Kılavuzu)

Bu rubrik Stage 1 prompt'una dahil edilir ve LLM'in bu skalaya göre puanlama yapması istenir:

```
RUBRIC START

CLARITY (of the ANSWER):
- 1.0 = Answer is clear, well-structured, easy to understand, no contradictions.
- 0.7 = Generally understandable, minor ambiguity or slight redundancy.
- 0.4 = Convoluted, hard to follow, contains contradictory statements, or uses excessive hedging.
- 0.0 = Nonsensical, unparseable, or riddled with contradictions.

SPECIFICITY (of the ANSWER):
- 1.0 = Answer provides concrete details: names, numbers, dates, specific facts.
- 0.7 = Reasonably specific with some concrete details.
- 0.4 = Mostly vague or generic, lacks concrete details.
- 0.0 = Completely vague, no specific information whatsoever.

IS_OFF_TOPIC:
- true  = The ANSWER does not address the question at all; it discusses an entirely unrelated topic.
- false = The ANSWER makes a genuine attempt to address the question, even if partially or incorrectly.

COHERENCE:
- 1.0 = Fluent, logical, no contradictions.
- 0.7 = Generally coherent, minor disconnects.
- 0.4 = Notable disconnects or contradictions.
- 0.0 = Incoherent / nonsensical.

HELPFULNESS:
- 1.0 = Directly solves the user's goal, actionable.
- 0.7 = Helpful but incomplete or superficial.
- 0.4 = Partially helpful.
- 0.0 = Useless / irrelevant.

IS_DEFLECTION:
- true  = Contains deflection ("I don't know", "I can't help") with no substantive information.
- false = Genuine attempt to answer with content.

RUBRIC END
```

### Stage 2: JSON Dönüşümü

Stage 1'in serbest metin çıktısı, ayrı bir LLM çağrısıyla yapısal JSON'a dönüştürülür:

**System Prompt:**
```
You are a JSON converter assistant.
Convert the given reasoning text into a single valid JSON object.
Output ONLY JSON, nothing else.
Float values must be between 0.0 and 1.0.
Boolean values must be true/false.
```

**Çıktı JSON Schema:**
```json
{
  "clarity": number,
  "specificity": number,
  "is_off_topic": boolean,
  "completeness": number,
  "coherence": number,
  "helpfulness": number,
  "is_deflection": boolean,
  "overall_score": number,
  "evaluation_confidence": number,
  "reasoning_summary": string,
  "disagreement_claims": [
    {
      "context_quote": string,
      "context_quote_type": "instruction" | "factual claim",
      "answer_quote": string,
      "reasoning": string,
      "disagreement_type": "agreement" | "unsupported claim" | "confirmed contradiction"
    }
  ]
}
```

> **Hata durumu:** JSON parse başarısız olursa → repair prompt ile 3 retry → hepsi başarısızsa regex fallback.

---

### 3.1 clarity (Netlik)

| | |
|---|---|
| **Ne ölçer** | Cevabın ne kadar açık, anlaşılır ve iyi yapılandırılmış olduğu |
| **Neye bakar** | Sadece **CEVABA** bakar (soruya değil) |
| **Müşteriye ne demek** | "Cevabınız kullanıcı tarafından ilk okuyuşta anlaşılabiliyor mu?" |
| **Hesaplama** | LLM rubrik skalasına göre puanlar |
| **Model** | gpt-5.2 (Stage 1) |
| **Overall score ağırlığı** | %5 |

**Rubrik Skalası:**

| Skor | Ne Anlama Gelir |
|---:|---|
| **1.0** | Açık, iyi yapılandırılmış, kolay anlaşılır, çelişki yok |
| **0.7** | Genel olarak anlaşılır, ufak belirsizlik veya fazlalık var |
| **0.4** | Karmaşık, takibi zor, çelişkili ifadeler veya aşırı muğlaklık |
| **0.0** | Anlamsız, okunamaz veya çelişkilerle dolu |

**Örnekler:**
- ✅ `1.0` → "PostgreSQL'de B-tree index, eşitlik ve aralık sorgularını hızlandırır. Hash index ise sadece eşitlik sorgularında çalışır."
- ⚠️ `0.4` → "Şey, bir nevi index denen şey var, belki hızlandırıyor olabilir, net değil aslında, yani bir bakıma..."

---

### 3.2 specificity (Özgüllük)

| | |
|---|---|
| **Ne ölçer** | Cevabın somut detay (isim, tarih, sayı, teknik terim) içerip içermediği |
| **Neye bakar** | Sadece **CEVABA** bakar |
| **Müşteriye ne demek** | "Cevap genel laflardan mı ibaret, yoksa somut isim/tarih/sayı veriyor mu?" |
| **Hesaplama** | LLM rubrik skalasına göre puanlar |
| **Model** | gpt-5.2 (Stage 1) |
| **Overall score ağırlığı** | ⚠️ **Dahil değil** — bağımsız sinyal olarak raporlanır |

**Rubrik Skalası:**

| Skor | Ne Anlama Gelir |
|---:|---|
| **1.0** | Somut detaylar: isimler, sayılar, tarihler, spesifik gerçekler |
| **0.7** | Makul ölçüde somut, bazı detaylar var |
| **0.4** | Çoğunlukla muğlak veya genel ("uzun zaman önce", "birçok kişi") |
| **0.0** | Tamamen belirsiz, hiçbir spesifik bilgi yok |

> **Neden overall_score'a dahil değil?** Bazı sorular doğası gereği genel cevap gerektirir (evet/hayır soruları gibi); specificity her durumda yüksek olması gereken bir metrik değildir.

---

### 3.3 coherence (Tutarlılık)

| | |
|---|---|
| **Ne ölçer** | Cevabın iç tutarlılığı — cümlelerin birbiriyle mantıksal uyumu |
| **Neye bakar** | Sadece **CEVABA** bakar |
| **Müşteriye ne demek** | "Cevaptaki cümleler birbiriyle çelişmiyor mu? Mantıklı bir bütün oluşturuyor mu?" |
| **Hesaplama** | LLM rubrik skalasına göre puanlar |
| **Model** | gpt-5.2 (Stage 1) |
| **Overall score ağırlığı** | %10 |

**Rubrik Skalası:**

| Skor | Ne Anlama Gelir |
|---:|---|
| **1.0** | Akıcı, mantıksal, çelişkisiz |
| **0.7** | Genel tutarlı, ufak kopukluklar |
| **0.4** | Belirgin kopukluklar veya çelişkiler |
| **0.0** | Tutarsız / anlamsız |

**Örnekler:**
- ✅ `1.0` → "Redis asenkron replikasyon kullanır. Bu sayede primary yazma performansını korur."
- ❌ `0.4` → "Redis senkron replikasyon kullanır. Aslında asenkrondur ama bazı durumlarda belki senkron."

---

### 3.4 helpfulness (Yardımcılık)

| | |
|---|---|
| **Ne ölçer** | Cevabın kullanıcının amacını karşılayıp karşılamadığı, eyleme dönüştürülebilir olup olmadığı |
| **Neye bakar** | **CEVAP + SORU** birlikte (sorunun ne istediğine göre cevabın faydalılığı) |
| **Müşteriye ne demek** | "Bu cevabı alan kullanıcı sorununu çözebildi mi?" |
| **Hesaplama** | LLM rubrik skalasına göre puanlar |
| **Model** | gpt-5.2 (Stage 1) |
| **Overall score ağırlığı** | %10 |

**Rubrik Skalası:**

| Skor | Ne Anlama Gelir |
|---:|---|
| **1.0** | Kullanıcının hedefini doğrudan çözer, eyleme dönük bilgi verir |
| **0.7** | Faydalı ama eksik veya yüzeysel |
| **0.4** | Kısmen faydalı |
| **0.0** | Tamamen işe yaramaz / alakasız |

**Örnekler:**
- ✅ `1.0` → "OOMKilled çözmek için: 1) Pod memory limit artırın, 2) Memory profiling yapın, 3) resources.requests ayarlayın."
- ❌ `0.0` → "DNS cache temizleyin." (soruyla alakasız öneri)

---

## 4. RAG Analitik Metrikleri (Paralel — Grounding & Kapsam)

Bu metrikler **rubrik puanlama değil, sayısal analiz** yapar. Her biri ayrı bir LLM çağrısıyla çalışır ve **birbirinden bağımsız olarak paralel** hesaplanır. Yöntem claim/statement bazlı: LLM önce parçalar çıkarır, sonra her parçayı sınıflar, oran hesaplanır.

---

### 4.1 answer_relevancy (Cevap İlgililiği)

| | |
|---|---|
| **Ne ölçer** | Cevaptaki ifadelerin soruyla ne kadar ilgili olduğu |
| **Neye bakar** | **CEVAP + SORU** |
| **Müşteriye ne demek** | "Cevaptaki cümlelerin ne kadarı gerçekten soruyu cevaplıyor, ne kadarı dolgu/konu dışı?" |
| **Model** | gpt-5-mini |
| **Overall score ağırlığı** | %15 |

**Hesaplama Formülü:**

```
answer_relevancy = ilgili_ifade_sayısı / toplam_ifade_sayısı
```

**Hesaplama Adımları:**
1. LLM, cevabı atomik ifadelere (statements) ayırır
2. Her ifade soruyla ilgili mi sınıflanır: `relevant: true/false`
3. Oran hesaplanır

**Arka Planda Çalışan Prompt:**

```
You are an answer relevancy evaluation expert. Your task:
1. Decompose the given answer into individual statements (atomic factual or
   informational claims).
2. For each statement, determine whether it is RELEVANT to the user's question.

Rules:
- Extract ALL distinct statements from the answer.
- A statement is "relevant" if it directly addresses, partially addresses, or provides
  useful context for the question.
- A statement is "not_relevant" if it is off-topic, tangential, or does not help answer
  the question.
- Filler phrases like "Sure, here is the answer" are not_relevant.
- Provide a brief reason for each classification.
- Output ONLY JSON, nothing else.
```

**LLM'e Gönderilen User Prompt:**
```
QUESTION:
{soru}

ANSWER:
{cevap}

Decompose the answer into statements and classify each as relevant or not_relevant
to the question. Output ONLY JSON.
```

**JSON Çıktı Yapısı:**
```json
{
  "statements": [
    {
      "statement": "Cevaptaki bir ifade",
      "relevant": true,
      "reason": "Soruyu doğrudan cevaplıyor"
    }
  ]
}
```

**Somut Örnek:**
```
Soru: "Fransa'nın başkenti neresi?"
Cevap: "Fransa'nın başkenti Paris'tir. İtalya pizza ile ünlüdür."

LLM çıktısı:
  statement: "Fransa'nın başkenti Paris'tir"  → relevant: true
  statement: "İtalya pizza ile ünlüdür"       → relevant: false

Skor = 1/2 = 0.50
```

---

### 4.2 hallucination_score (Halüsinasyon Skoru)

| | |
|---|---|
| **Ne ölçer** | Cevaptaki uydurma bilgi oranı (**ters çevrilmiş**: 1.0 = iyi) |
| **Neye bakar** | **CEVAP + CONTEXT** üzerinde claim-level disagreement analizi |
| **Müşteriye ne demek** | "Ne kadar az uydurma var? 1.0 = hiç uydurma yok, 0.0 = tamamen uydurma" |
| **Model** | gpt-5-mini (dedicated two-stage judge) |
| **Overall score ağırlığı** | %25 (en yüksek) |

**Hesaplama Formülü:**

```
hallucination_score = 1.0 - (
  0.6 × unsupported_claim_sayısı +
  1.0 × confirmed_contradiction_sayısı
) / toplam_claim
```

**Nasıl çalışır (Datadog-style two-stage pipeline):**
1. Stage 1: Cevaptan atomic claim'ler çıkarılır ve her claim için `agreement | unsupported claim | confirmed contradiction` etiketi üretilir (CoT reasoning ile).
2. Stage 2: Bu reasoning metni strict JSON şemasına dönüştürülür (`hallucination_claims[]`).
3. Skor, disagreement tiplerinin oranından deterministik hesaplanır.

**Ağırlıklı Ceza Sistemi:**
- `agreement` → 0 ceza (destekleniyor)
- `unsupported claim` → 0.6 ceza (context'te bilgi yok ama çelişmiyor)
- `confirmed contradiction` → 1.0 ceza (context ile açık çelişki)

> **Neden ağırlıklı?** "Context'te bilgi yok" ile "context'in söylediğine aykırı" farklı ciddiyet düzeyleridir. Unsupported claim her zaman hallucination olmayabilir (doğru ama kaynak dışı bilgi olabilir), contradiction ise kesin hata.

**Paraphrase / Borderline Kılavuzu:**
Prompt, LLM'e şu ek yönlendirmeyi verir:
- Cevap context'i **farklı kelimelerle özetliyorsa** veya **makul bir çıkarım yapıyorsa** → `agreement`. Birebir kelime eşleşmesi gerekmez.
- `unsupported claim` sadece context konuyla ilgili **hiçbir şey söylemiyorsa** kullanılır.
- `confirmed contradiction` sadece context'in **açıkça tersini ifade ettiği** durumlarda kullanılır.

> **Örnek:** Context "typical use cases include session caching, pub/sub, leaderboards" → cevap "Redis çoğunlukla cache olarak kullanılır" → `agreement` (context'in özeti).

**Somut Örnek:**
```
5 iddia: 3 agreement + 1 unsupported + 1 contradiction
hallucination_score = 1.0 - (0.6×1 + 1.0×1) / 5 = 1.0 - 0.32 = 0.68
```

**Özel Durum:** Context listesi boşsa → hallucination_score `null` döner (ölçülemez).

---

### 4.3 completeness (Tamlık)

| | |
|---|---|
| **Ne ölçer** | Cevabın, soruda sorulan tüm bilgi noktalarını kapsayıp kapsamadığı |
| **Neye bakar** | **SORU + CEVAP + CONTEXT** |
| **Müşteriye ne demek** | "Sorunun tüm parçaları cevaplandı mı, yoksa bazı kısımlar atlandı mı?" |
| **Model** | gpt-5-mini |
| **Overall score ağırlığı** | %15 |

**Hesaplama Formülü:**

```
completeness = Σ(status_ağırlığı) / kilit_nokta_sayısı

status_ağırlıkları:
  covered           = 1.0
  partially_covered = 0.5
  not_covered       = 0.0
```

**Hesaplama Adımları:**
1. LLM, soru ve context'ten 2-6 adet kilit bilgi noktası (key points) çıkarır
2. Her kilit nokta için cevap kontrol edilir: covered / partially_covered / not_covered
3. Ağırlıklı oran hesaplanır

**Arka Planda Çalışan Prompt:**

```
You are a completeness evaluation expert. Your task:
1. Extract the key information requirements (key points) from the question and contexts.
2. For each key point, determine whether the answer adequately covers it.

Rules:
- Extract 2-6 key points depending on question complexity.
  Simple questions may have 2-3, complex ones up to 6.
- Each key point should be a distinct, verifiable information requirement.
- A key point is "covered" if the answer addresses it with relevant, substantive
  information.
- A key point is "not_covered" if the answer ignores it or provides no relevant
  information.
- A key point is "partially_covered" if the answer touches on it but lacks important
  details.
- Output ONLY JSON, nothing else.
```

**LLM'e Gönderilen User Prompt:**
```
QUESTION:
{soru}

ANSWER:
{cevap}

CONTEXT PASSAGES:
[0] {context 0}
[1] {context 1}
...

Extract key points from the question and verify which ones the answer covers.
Output ONLY JSON.
```

**JSON Çıktı Yapısı:**
```json
{
  "key_points": [
    {
      "point": "Kilit nokta açıklaması",
      "status": "covered | partially_covered | not_covered",
      "evidence": "Cevaptaki kanıt veya yokluğu"
    }
  ]
}
```

**Somut Örnek:**
```
Soru: "Retriever ve reranker arasındaki fark nedir?"
Kilit noktalar:
  1. "Retriever'ın ne olduğu ve rolü"       → covered (1.0)
  2. "Reranker'ın ne olduğu ve rolü"         → covered (1.0)
  3. "İkisi arasındaki temel fark"           → partially_covered (0.5)

Skor = (1.0 + 1.0 + 0.5) / 3 = 0.833
```

---

### 4.4 citation_check (Kaynak Atfı Doğruluğu)

| | |
|---|---|
| **Ne ölçer** | Cevaptaki `[1]`, `[Source 2]` gibi atıfların doğru kaynağa mı referans verdiği |
| **Neye bakar** | **CEVAP + CONTEXT** |
| **Müşteriye ne demek** | "Cevap 'Kaynak 2'ye göre...' diyorsa, Kaynak 2 gerçekten o bilgiyi içeriyor mu?" |
| **Model** | gpt-5-mini |
| **Overall score ağırlığı** | Dahil değil (opsiyonel metrik) |

**Hesaplama Formülü:**

```
citation_check = doğru_atıf_sayısı / toplam_atıf_sayısı
```

**Özel Durumlar:**
- Cevapta hiç atıf kalıbı yoksa → `null` (metrik uygulanmaz)
- Atıf var ama context listesi boşsa → `0.0` (tüm atıflar yanlış)
- LLM atıf bulamadıysa → `1.0`

**Tanınan Atıf Formatları:** `[1]`, `[2]`, `[Source 1]`, `(bkz. context 1)`

**Arka Planda Çalışan Prompt:**

```
You are a citation verification expert. Your task: verify source citations in the
given answer against the provided context passages.

Context passages are numbered starting from [0]. Common citation formats: [1], [2],
[Source 1], (see context 1), etc.

For each citation found in the answer:
1. Determine which context passage index (0-based) the citation claims to reference.
2. Check if that context index actually exists in the provided passages.
3. If the index exists, verify whether that passage contains the information being cited.

Verdict rules:
- "correct": Citation references a valid context index AND that passage supports the
  cited claim.
- "incorrect": Citation references a non-existent context index, OR the referenced
  passage does not contain the cited information.

IMPORTANT: A citation like [Source 99] or [15] is INCORRECT if there are fewer than
100 or 16 context passages, respectively. Always check that the referenced index is
within bounds.

If no citations exist, return an empty array.
Output ONLY JSON, nothing else.
```

**LLM'e Gönderilen User Prompt:**
```
ANSWER:
{cevap}

CONTEXT PASSAGES ({n} total, indexed 0 to {n-1}):
[0] {context 0}
[1] {context 1}
...

Find and verify all source citations in the answer.
Any citation referencing an index outside 0-{n-1} is INCORRECT.
If no citations exist, return an empty array. Output ONLY JSON.
```

**JSON Çıktı Yapısı:**
```json
{
  "citations": [
    {
      "citation_text": "[Source 1]",
      "referenced_context_index": 1,
      "verdict": "correct | incorrect",
      "reason": "Context 1 bu bilgiyi içeriyor/içermiyor"
    }
  ]
}
```

---

### 4.5 context_precision (Bağlam Hassasiyeti)

| | |
|---|---|
| **Ne ölçer** | Retriever'ın getirdiği belgelerin soruyla ne kadar ilgili olduğu |
| **Neye bakar** | **SORU + CONTEXT** (cevaba bakmaz!) |
| **Müşteriye ne demek** | "Arama motoru gereksiz belge getiriyor mu? Getirdiği her belge gerçekten soruyla ilgili mi?" |
| **Model** | gpt-5-mini |
| **Overall score ağırlığı** | %15 |

**Hesaplama Formülü:**

```
context_precision = ilgili_context_sayısı / toplam_context_sayısı
```

**Hesaplama Adımları:**
1. Her context parçası LLM tarafından soruyla ilgili mi sınıflanır: `relevant: true/false`
2. Oran hesaplanır

**Arka Planda Çalışan Prompt:**

```
You are a context relevance evaluation expert. Your task: evaluate whether each
provided context passage is useful for answering the given question.

Rules:
- For each context passage, determine if it contains information that helps answer
  the question.
- A context is "relevant" if it directly provides, partially provides, or gives useful
  background for answering the question.
- A context is "not_relevant" if it is off-topic, contains no useful information for
  the question, or is entirely unrelated.
- Provide a brief reason for each classification.
- Output ONLY JSON, nothing else.
```

**LLM'e Gönderilen User Prompt:**
```
QUESTION:
{soru}

CONTEXT PASSAGES ({n} total):
[0] {context 0}
[1] {context 1}
...

For each context passage, determine if it is relevant to answering the question.
Output ONLY JSON.
```

**JSON Çıktı Yapısı:**
```json
{
  "contexts": [
    {
      "index": 0,
      "relevant": true,
      "reason": "Soruyu doğrudan cevaplayacak bilgi içeriyor"
    }
  ]
}
```

**Somut Örnek:**
```
Soru: "PostgreSQL index ne işe yarar?"
Context[0]: "PostgreSQL index'leri sorguları hızlandırır."  → relevant: true
Context[1]: "Koalalar Avustralya'da yaşar."                → relevant: false

Skor = 1/2 = 0.50
```

---

### 4.6 context_recall (Bağlam Kapsamı)

| | |
|---|---|
| **Ne ölçer** | Doğru cevap için gereken bilgilerin context'te bulunup bulunmadığı |
| **Neye bakar** | **SORU + CONTEXT + GROUND_TRUTH** (varsa) |
| **Müşteriye ne demek** | "Cevaplayabilmek için gerekli bilgilerin ne kadarı getirilen belgelerde mevcut?" |
| **Model** | gpt-5-mini |
| **Overall score ağırlığı** | %10 |

**Hesaplama Formülü:**

```
context_recall = bulunan_bilgi_sayısı / toplam_bilgi_ihtiyacı
```

**İki Mod:**
- **Ground truth varsa:** GT cümlelere ayrılır → her cümle contextte aranır
- **Ground truth yoksa:** Sorudan 2-6 bilgi ihtiyacı çıkarılır → contextte aranır

**Arka Planda Çalışan Prompt:**

```
You are a context recall evaluation expert. Your task: determine how well the
provided context passages cover the information needed to answer the question.

You will receive EITHER a ground truth answer OR just the question.

If ground truth is provided:
1. Decompose the ground truth answer into individual factual statements.
2. For each statement, check if any context passage contains this information.

If only a question is provided (no ground truth):
1. Identify the key information needs required to fully answer the question (2-6 needs).
2. For each need, check if any context passage provides this information.

Verdicts:
- "found": The information is present in at least one context passage.
- "not_found": None of the context passages contain this information.

Provide a brief reason for each verdict.
Output ONLY JSON, nothing else.
```

**LLM'e Gönderilen User Prompt (ground truth varsa):**
```
GROUND TRUTH ANSWER:
{ground_truth}

CONTEXT PASSAGES ({n} total):
[0] {context 0}
[1] {context 1}
...

Decompose the ground truth into factual statements and check if each is found
in the contexts. Output ONLY JSON.
```

**LLM'e Gönderilen User Prompt (ground truth yoksa):**
```
QUESTION:
{soru}

CONTEXT PASSAGES ({n} total):
[0] {context 0}
[1] {context 1}
...

Identify the key information needs to answer the question and check if each is
found in the contexts. Output ONLY JSON.
```

**JSON Çıktı Yapısı:**
```json
{
  "items": [
    {
      "statement": "Bilgi ifadesi veya ihtiyaç",
      "verdict": "found | not_found",
      "reason": "Context X'te bulundu / Hiçbir context'te yok"
    }
  ]
}
```

**Somut Örnek:**
```
Ground Truth: "Retriever ilk aşamada belge getirir. Reranker ikinci aşamada sıralar."
Context[0]: "Retriever, büyük belge havuzundan ilgili belgeleri getirir."
Context[1]: "Reranker, getirilen belgeleri ilgililik sırasına göre yeniden sıralar."

LLM çıktısı:
  statement: "Retriever ilk aşamada belge getirir" → found
  statement: "Reranker ikinci aşamada sıralar"     → found

Skor = 2/2 = 1.00
```

---

## 5. Bayraklar (Flags)

Bayraklar sayısal skor değil, `true` / `false` değer döner. Stage 1 rubrik değerlendirmesinde belirlenir.

### 5.1 is_off_topic

| | |
|---|---|
| **Ne tespit eder** | Cevabın soruyla tamamen alakasız bir konudan bahsedip bahsetmediği |
| **Neye bakar** | **CEVAP + SORU** birlikte |
| **Müşteriye ne demek** | "Sistem tamamen alakasız bir cevap mı vermiş?" |
| **Overall score'a etkisi** | **Doğrudan:** `is_off_topic=true` olduğunda overall_score **max 0.20** ile sınırlandırılır (cap) |

**Rubrik:**
- `true` = Cevap soruyu hiç ele almıyor; tamamen alakasız bir konudan bahsediyor
- `false` = Cevap soruyu cevaplamaya çalışıyor, kısmen veya yanlış olsa bile

**Neden cap uygulanıyor?** İçerik tamamen konu dışıysa cevap ne kadar akıcı olursa olsun gerçek kalite düşüktür. Bu cap, alakasız ama "iyi yazılmış" cevapların overall_score'u şişirmesini engeller.

**Deterministik hard-override (off-topic kaçırmalarını azaltma):**
- LLM `is_off_topic` değerini yanlış üretse bile, kod tarafında ek bir kontrol yapılır.
- Eğer `answer_relevancy == 0.0` **ve** `helpfulness == 0.0` ise `is_off_topic = true` olarak **zorlanır** (hard-override, LLM'in boolean'ından önce çalışır).
- Bu durumda off-topic cap otomatik devreye girer (`overall_score <= 0.20`).

### 5.2 is_deflection

| | |
|---|---|
| **Ne tespit eder** | Cevabın kaçamak olup olmadığı ("Bilmiyorum", "Yardım edemem" vs.) |
| **Neye bakar** | **CEVABA** bakar |
| **Müşteriye ne demek** | "Sistem gerçek bir cevap vermek yerine geçiştirme mi yapıyor?" |
| **Overall score'a etkisi** | **Doğrudan:** `is_deflection=true` olduğunda overall_score **max 0.20** ile sınırlandırılır (cap) |

**Rubrik:**
- `true` = "I don't know", "I can't help" benzeri ifade + substantif bilgi yok
- `false` = İçerikli bir cevap verme girişimi

**Neden cap uygulanıyor?** Deflection cevaplarda LLM bazen "nazikçe reddetti, coherent, clarity yüksek" diye yüksek skor verebiliyor. Cap, geçiştirme cevapların geçersiz şekilde yüksek overall_score almasını önler.

---

## 6. overall_score — Bileşik Skor

| | |
|---|---|
| **Ne ölçer** | Tüm metriklerin ağırlıklı ortalaması — tekil kalite puanı |
| **LLM çağrısı** | ⚠️ **Yok** — tamamen kod tarafında hesaplanır |
| **Aralık** | 0.0 – 1.0 |

**Formül:**

```
overall_score = Σ(metrik_değeri × ağırlık) / Σ(ağırlık)
```

`null` olan metrikler atlanır ve toplam ağırlık yeniden normalize edilir.

**Ağırlık Tablosu:**

| Metrik | Ağırlık | Yüzde | Neden bu ağırlık? |
|---|---:|---:|---|
| hallucination_score | 0.25 | %25 | Kaynaklara sadakat ve uydurma tespiti en kritik boyut |
| completeness | 0.15 | %15 | Eksik cevap kullanıcıyı tatmin etmez |
| answer_relevancy | 0.10 | %10 | Konu dışı dolgu kaliteyi düşürür |
| context_precision | 0.15 | %15 | Retriever kalitesi cevabı doğrudan etkiler |
| context_recall | 0.10 | %10 | Bilgi eksikliği doğru cevabı imkansız kılar |
| coherence | 0.10 | %10 | İç tutarlılık önemli ama az görülen sorun |
| helpfulness | 0.10 | %10 | Kullanıcı memnuniyeti |
| clarity | 0.05 | %5 | LLM'ler genelde net yazar; düşük varyans |
| **Toplam** | **1.00** | **%100** | |

**Dahil olmayanlar ve nedenleri:**
- `specificity` → Her soru somut detay gerektirmez
- `citation_check` → Opsiyonel; her cevap atıf içermez

### Score Cap Kuralları

Overall score hesaplandıktan sonra aşağıdaki koruyucu cap'ler uygulanır:

```python
_DEFLECTION_SCORE_CAP = 0.20
_OFF_TOPIC_SCORE_CAP = 0.20
_CONTRADICTION_SCORE_CAP = 0.35

# _compute_overall_score içinde:
if is_deflection and score is not None:
    score = min(score, _DEFLECTION_SCORE_CAP)

if is_off_topic and score is not None:
  score = min(score, _OFF_TOPIC_SCORE_CAP)

if has_contradiction and score is not None:
  score = min(score, _CONTRADICTION_SCORE_CAP)
```

**has_contradiction nasıl hesaplanır?** `hallucination_claims` içinde en az bir claim `disagreement_type="confirmed contradiction"` ise `has_contradiction=true` olur.

**Neden?**
- `is_deflection`: Geçiştirme cevapların yapay şekilde yüksek skor almasını önler.
- `is_off_topic`: Konu dışı cevapları, yazım kalitesi yüksek olsa da düşük bantta tutar.
- `contradicted`: Context ile açık çelişen iddialarda skorun gereksiz yükselmesini engeller.

**Off-topic hard-override neden gerekli?** Bazı örneklerde LLM, bariz alakasız cevabı `is_off_topic=false` olarak etiketleyebiliyor. Hard-override (answer_relevancy=0 + helpfulness=0 kontrolü) LLM'in boolean kararından **önce** çalışır ve bu false negative durumlarını tamamen ortadan kaldırır.

Birden fazla kural aynı anda aktifse en düşük cap uygulanır (ardışık `min()` davranışı).

**Yorumlama kılavuzu:**

| Aralık | Yorum |
|---|---|
| **0.85+** | Yüksek kalite — cevap güvenilir ve kapsamlı |
| **0.65–0.85** | Orta — bazı eksiklikler veya grounding sorunları var |
| **0.50–0.65** | Düşük-orta — önemli sorunlar mevcut |
| **<0.50** | Düşük — ciddi halüsinasyon, eksiklik veya alakasızlık |

**Kod referansı:** `app/evaluation/evaluator.py` → `_OVERALL_WEIGHTS` dict + `_compute_overall_score()` fonksiyonu

---

## 7. Ek Çıktılar

Metrik skorlarının yanı sıra her değerlendirme şu ek bilgileri de döner:

| Çıktı | Açıklama |
|---|---|
| `reasoning_summary` | Stage 1'in değerlendirme özeti (Türkçe/İngilizce) |
| `evaluation_confidence` | LLM'in kendi değerlendirmesine ne kadar güvendiği (0.0–1.0) |
| `disagreement_claims` | Cevap ile context arasındaki çelişki detayları |
| `completeness_key_points` | Her kilit noktanın point, status, evidence detayı |
| `stage_1_reasoning` | Stage 1 tam CoT reasoning metni |
| `model_used` | Hangi modellerin kullanıldığı (ör: "gpt-5.2 + gpt-5-mini") |
| `prompt_version` | Prompt versiyonu |
| `rubric_version` | Rubrik versiyonu |

---

## 8. SSS (Sık Sorulan Sorular)

**S: clarity, sorunun netliğini mi ölçer?**  
H: Hayır. clarity yalnızca **cevabın** anlaşılırlığını ölçer. Sorunun uzunluğu veya kalitesi clarity'yi etkilemez.

**S: Sorgunun kalitesini ölçen bir metrik var mı?**  
H: Şu an yok. `query_clarity`, `query_specificity`, `query_answerability` gibi sorgu kalitesi metrikleri ileride eklenebilir.

**S: Aynı soruyu farklı formulasyonlarla sorsam hangi metrikler değişir?**  
C: `answer_relevancy` ve `completeness` değişebilir (çünkü değerlendirme soruya bağlı). `clarity`, `coherence`, `hallucination_score` aynı kalır (çünkü cevap aynı).

**S: citation_check neden bazen null?**  
C: Cevapta hiçbir atıf formatı (`[1]`, `[Source 1]` vb.) tespit edilmezse metrik uygulanmaz ve `null` döner. Bu bir hata değil, metriğin o cevap için geçerli olmadığı anlamına gelir.

**S: context_precision vs context_recall farkı ne?**  
C: `context_precision` = "Getirilen belgelerin ne kadarı **işe yarıyor?**" (gürültü ölçer — gereksiz belge var mı?). `context_recall` = "Gerekli bilgilerin ne kadarı getirilen **belgelerde var?**" (eksiklik ölçer — gerekli belge getirilmemiş mi?).

**S: overall_score LLM tarafından mı hesaplanır?**  
C: Hayır. Overall score **tamamen kodda** ağırlıklı ortalama olarak hesaplanır. LLM çağrısı yoktur. Bu, tutarlılık ve tekrarlanabilirlik sağlar.

**S: specificity neden overall_score'a dahil değil?**  
C: Evet/hayır soruları, tanım soruları gibi türlerde yüksek specificity beklenmez. Her soru tipi için adil bir genel skor oluşturmak adına bağımsız sinyal olarak raporlanır.

**S: Toplamda kaç LLM çağrısı yapılıyor?**  
C: **8 adet** (normal akışta): Stage 1 (1) + Stage 2 (1) + 6 RAG metriği. Stage 2 JSON parse hatası olursa +1-3 retry olabilir.

**S: Hangi modeller kullanılıyor?**  
C: Stage 1: `gpt-5.2` (16384 max token), Stage 2 + tüm RAG metrikleri: `gpt-5-mini` (1024-4096 max token).

---

## 9. Kod Referans Haritası

| Bileşen | Dosya | Fonksiyon/Değişken |
|---|---|---|
| Rubrik tanımı | `app/evaluation/prompts.py` | `RUBRIC_BLOCK` |
| Stage 1 system prompt | `app/evaluation/prompts.py` | `STAGE_1_SYSTEM_PROMPT` |
| Stage 1 user prompt üretimi | `app/evaluation/prompts.py` | `build_stage_1_user_prompt()` |
| Stage 2 JSON dönüşüm prompt'u | `app/evaluation/prompts.py` | `STAGE_2_SYSTEM_PROMPT` |
| Stage 2 repair prompt'u | `app/evaluation/prompts.py` | `STAGE_2_REPAIR_SYSTEM_PROMPT` |
| JSON schema (Stage 2 çıktı) | `app/evaluation/prompts.py` | `STAGE_2_JSON_SCHEMA` |
| Answer relevancy prompt + schema | `app/evaluation/prompts.py` | `ANSWER_RELEVANCY_SYSTEM_PROMPT`, `ANSWER_RELEVANCY_JSON_SCHEMA` |
| Completeness prompt + schema | `app/evaluation/prompts.py` | `COMPLETENESS_SYSTEM_PROMPT`, `COMPLETENESS_JSON_SCHEMA` |
| Citation check prompt + schema | `app/evaluation/prompts.py` | `CITATION_CHECK_SYSTEM_PROMPT`, `CITATION_CHECK_JSON_SCHEMA` |
| Context precision prompt + schema | `app/evaluation/prompts.py` | `CONTEXT_PRECISION_SYSTEM_PROMPT`, `CONTEXT_PRECISION_JSON_SCHEMA` |
| Context recall prompt + schema | `app/evaluation/prompts.py` | `CONTEXT_RECALL_SYSTEM_PROMPT`, `CONTEXT_RECALL_JSON_SCHEMA` |
| Overall score ağırlıkları | `app/evaluation/evaluator.py` | `_OVERALL_WEIGHTS` |
| Score cap sabitleri | `app/evaluation/evaluator.py` | `_DEFLECTION_SCORE_CAP`, `_OFF_TOPIC_SCORE_CAP`, `_CONTRADICTION_SCORE_CAP` |
| Çelişki tespiti yardımcı fonksiyonu | `app/evaluation/evaluator.py` | `_has_contradicted_claims()` |
| Off-topic hard-override yardımcı fonksiyonu | `app/evaluation/evaluator.py` | `_coerce_off_topic_flag()` |
| Overall score hesaplama | `app/evaluation/evaluator.py` | `_compute_overall_score()` |
| Evaluation ana giriş noktası | `app/evaluation/evaluator.py` | `evaluate_trace()` |
| RAG metrics orchestrator | `app/evaluation/rag_metrics.py` | `compute_rag_metrics()` |
| Hallucination dedicated judge | `app/evaluation/rag_metrics.py` | `compute_hallucination_rubric()` |
| Atıf format tespiti | `app/evaluation/rag_metrics.py` | `has_citations()`, `_CITATION_PATTERN` |
| LLM client | `app/evaluation/llm_client.py` | `OpenAILLMClient.chat_completion()` |
| Model + rollout konfigürasyonu | `app/config.py` | `stage_1_model`, `stage_2_model`, `rag_metrics_model`, `hallucination_prompt_version` |
