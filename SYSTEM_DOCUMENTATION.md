# RAG Eval API — Sistem Dokümantasyonu

**Tarih:** 10 Mart 2026  
**Durum:** Kaynak gerçeklik dokümanı  
**Kapsam:** Bu doküman yalnızca kodda gerçekten çalışan özellikleri anlatır.

---

## İçindekiler

1. [Amaç ve Kapsam](#1-amaç-ve-kapsam)
2. [Sistemin Ne Yaptığı](#2-sistemin-ne-yaptığı)
3. [Yüksek Seviye Mimari](#3-yüksek-seviye-mimari)
4. [Ana Bileşenler](#4-ana-bileşenler)
5. [API Yüzeyi](#5-api-yüzeyi)
6. [Kimlik Doğrulama ve Güvenlik](#6-kimlik-doğrulama-ve-güvenlik)
7. [Trace Yaşam Döngüsü](#7-trace-yaşam-döngüsü)
8. [Evaluation Pipeline](#8-evaluation-pipeline)
   - [8.1 Evaluation Akışının Teknik Analizi](#evaluation-akisinin-teknik-analizi)
  - [8.1.1 Evaluation Felsefesi / Tasarım Prensibi](#evaluation-felsefesi-tasarim-prensibi)
  - [8.1.2 Worked Example](#worked-example)
  - [8.1.3 Failure Mode Kataloğu](#failure-mode-katalogu)
  - [8.1.4 Metric Rationale](#metric-rationale)
  - [8.1.5 Weight & Cap Rationale](#weight-cap-rationale)
  - [8.1.6 False Positive / False Negative Beklentileri](#false-positive-false-negative-beklentileri)
  - [8.1.7 Numeric End-to-End Example](#numeric-end-to-end-example)
  - [8.2 Stage 1 — Rubric Reasoning](#82-stage-1--rubric-reasoning)
  - [8.3 Stage 2 — JSON Extraction](#83-stage-2--json-extraction)
  - [8.4 RAG Metrics Pipeline](#84-rag-metrics-pipeline)
  - [8.5 Hata Davranışı ve Fallback](#85-hata-davranışı-ve-fallback)
  - [8.6 Operasyonel Akış Özeti](#86-operasyonel-akış-özeti)
  - [8.7 Teknik Değerlendirme Özeti](#87-teknik-değerlendirme-özeti)
9. [Metrikler](#9-metrikler)
10. [Overall Score Hesabı](#10-overall-score-hesabı)
11. [Multi-Agent / Step Evaluation](#11-multi-agent--step-evaluation)
12. [Webhook Davranışı](#12-webhook-davranışı)
13. [Veri Modeli](#13-veri-modeli)
14. [Konfigürasyon](#14-konfigürasyon)
15. [Çalıştırma ve Ortamlar](#15-çalıştırma-ve-ortamlar)
16. [Testler ve Doğrulama](#16-testler-ve-doğrulama)
17. [Bilinen Sınırlar](#17-bilinen-sınırlar)

---

## 1. Amaç ve Kapsam

Bu proje, RAG ve agent tabanlı sistemlerin ürettiği cevapları otomatik olarak değerlendirir.

Sistem şunları yapar:

- soru-cevap-context trace'lerini alır
- bunları veritabanına kaydeder
- LLM destekli bir evaluation pipeline çalıştırır
- metrik skorları, bayraklar ve açıklayıcı detaylar üretir
- sonuçları API üzerinden döner
- istenirse webhook ile dış sisteme iletir

Bu doküman, mevcut uygulamanın çalışan halini anlatır. Roadmap, plan veya geçmiş sprint hedefleri bu dokümanın konusu değildir.

---

## 2. Sistemin Ne Yaptığı

Ürün, temel olarak bir **evaluation backend**'dir.

Başlıca yetenekler:

- kullanıcı kaydı ve API key ile kimlik doğrulama
- tekli ve toplu trace ingest
- sync veya async evaluation çalıştırma
- trace listesi ve trace detaylarını döndürme
- metric tanımlarını public endpoint üzerinden verme
- çok adımlı agent trace'leri için step-level evaluation yapabilme
- token, cost ve evaluation süresi takibi
- content hash üzerinden sonuç cache'leme
- webhook callback gönderme

---

## 3. Yüksek Seviye Mimari

```text
Client / SDK / Integrator
          |
          | HTTP
          v
     FastAPI Application
          |
          +--> Auth Router
          +--> Ingest Router
          +--> Traces Router
          +--> Metrics Router
          |
          v
    Service Layer / Orchestration
          |
          +--> Evaluation Pipeline
          |      +--> Stage 1 rubric reasoning
          |      +--> Stage 2 JSON extraction
          |      +--> RAG metrics (parallel)
          |
          +--> Webhook delivery
          +--> Cache lookup / persistence
          |
          v
      PostgreSQL

Optional async path:
FastAPI -> Redis -> Celery worker -> Evaluation Service
```

---

## 4. Ana Bileşenler

### Uygulama giriş noktası
- [app/main.py](app/main.py)

### Router'lar
- [app/routers/auth.py](app/routers/auth.py)
- [app/routers/ingest.py](app/routers/ingest.py)
- [app/routers/traces.py](app/routers/traces.py)
- [app/routers/metrics.py](app/routers/metrics.py)

### Servis katmanı
- [app/services/auth_service.py](app/services/auth_service.py)
- [app/services/ingest_service.py](app/services/ingest_service.py)
- [app/services/evaluation_service.py](app/services/evaluation_service.py)
- [app/services/webhook_service.py](app/services/webhook_service.py)

### Evaluation engine
- [app/evaluation/evaluator.py](app/evaluation/evaluator.py)
- [app/evaluation/rag_metrics.py](app/evaluation/rag_metrics.py)
- [app/evaluation/prompts.py](app/evaluation/prompts.py)
- [app/evaluation/llm_client.py](app/evaluation/llm_client.py)

### Veri modelleri
- [app/models/user.py](app/models/user.py)
- [app/models/trace.py](app/models/trace.py)
- [app/models/evaluation.py](app/models/evaluation.py)

### Altyapı
- [docker-compose.yml](docker-compose.yml)
- [Dockerfile](Dockerfile)
- [app/tasks/celery_app.py](app/tasks/celery_app.py)
- [app/tasks/evaluation_tasks.py](app/tasks/evaluation_tasks.py)

---

## 5. API Yüzeyi

Mevcut HTTP yüzeyi aşağıdaki endpoint'lerden oluşur.

### Auth

#### `POST /api/v1/auth/register`
Yeni kullanıcı oluşturur, tam API key'i yalnızca bu aşamada döner.

#### `POST /api/v1/auth/login`
Kullanıcı doğrulaması yapar. Güvenlik nedeniyle tam API key dönmez; yalnızca prefix döner.

### Ingest

#### `POST /api/v1/ingest`
Tek trace alır ve evaluation başlatır.

#### `POST /api/v1/ingest/batch`
En fazla 100 trace'i tek istekte alır ve toplu evaluation başlatır.

### Trace sorgulama

#### `GET /api/v1/traces`
Kullanıcının trace'lerini sayfalanmış biçimde listeler.

#### `GET /api/v1/traces/{id}`
Tek trace döner. `detail=summary` veya `detail=full` destekler.

### Public yardımcı endpoint'ler

#### `GET /api/v1/metrics/definitions`
Metric kataloğunu döner. Public'tir.

#### `GET /health`
API, PostgreSQL ve Redis sağlık bilgisini döner. Public'tir.

### Açıkça önemli not

Auth gereksinimi şu şekildedir:

- **auth endpoint'leri:** public
- **metrics definitions:** public
- **health:** public
- **diğer business endpoint'leri:** `X-API-Key` gerekir

---

## 6. Kimlik Doğrulama ve Güvenlik

### Kimlik doğrulama modeli

Sistem `X-API-Key` header'ı ile çalışır.

Akış:

1. kullanıcı `register` ile oluşturulur
2. sistem tam API key üretir ve sadece o anda döner
3. sonraki isteklerde istemci bu key'i `X-API-Key` ile gönderir
4. middleware hash üzerinden kullanıcıyı bulur

İlgili kod:
- [app/middleware/auth.py](app/middleware/auth.py)
- [app/services/auth_service.py](app/services/auth_service.py)

### Rate limit'ler

Router seviyesinde rate limit uygulanır:

- `register`: 3/dakika
- `login`: 5/dakika
- `ingest`: 30/dakika
- `ingest/batch`: 10/dakika

### Webhook güvenliği

Webhook hedefleri için:

- sadece `https` kabul edilir
- `localhost`, `db`, `redis`, `api`, `worker`, `pgadmin` gibi hostlar engellenir
- DNS çözümleme sonrası private/reserved IP kontrolü yapılır
- istenirse payload HMAC-SHA256 ile imzalanır

İlgili kod:
- [app/services/webhook_service.py](app/services/webhook_service.py)

---

## 7. Trace Yaşam Döngüsü

Bir trace'in sistem içindeki yaşam döngüsü:

1. istemci trace gönderir
2. trace `pending` statüsüyle DB'ye kaydedilir
3. evaluation tetiklenir
4. cache hit varsa mevcut sonuç kopyalanır
5. cache miss ise evaluator çalışır
6. sonuçlar `evaluation_results` tablosuna yazılır
7. trace `completed` veya `failed` statüsüne alınır
8. webhook varsa callback gönderilir

Temel akış kaynakları:
- [app/services/ingest_service.py](app/services/ingest_service.py)
- [app/services/evaluation_service.py](app/services/evaluation_service.py)

---

## 8. Evaluation Pipeline

Evaluation pipeline iki ana dalın paralel çalışmasıyla oluşur:

```text
                    Trace
                      |
          +-----------+-----------+
          |                       |
          v                       v
  Rubric pipeline          RAG metrics pipeline
  (Stage 1 -> Stage 2)     (parallel analytical calls)
          |                       |
          +-----------+-----------+
                      |
                      v
             Merge + overall_score
```

<a id="evaluation-akisinin-teknik-analizi"></a>

### 8.1 Evaluation Akışının Teknik Analizi

Bu bölüm, evaluation tasarımını sadece kavramsal olarak değil, doğrudan kod üstünden incelenebilmesi için detaylandırılmıştır. Amaç şu sorulara cevap vermektir:

- sistem hangi sırayla ne yapıyor?
- hangi parçalar kaliteyi artırıyor?
- hangi parçalar latency ve cost üretiyor?
- hangi kararlar bilinçli trade-off, hangileri potansiyel zayıflık?

<a id="evaluation-felsefesi-tasarim-prensibi"></a>

#### 8.1.1 Evaluation Felsefesi / Tasarım Prensibi

Bu sistemin evaluation mantığı tek cümlede şudur:

> Cevabı sadece "iyi yazılmış mı?" diye değil, aynı zamanda "gerçekten soruya hizmet ediyor mu, verilen context'e dayanıyor mu ve ürün açısından güvenli mi?" diye değerlendirmek.

Bu nedenle tasarım tek bir judge çağrısına bırakılmamıştır. Sistem, bilinçli olarak üç farklı düşünceyi bir araya getirir:

1. **Yazı ve kullanıcı faydası kalitesi**
  - cevap açık mı?
  - akıcı mı?
  - kullanıcıya yardımcı mı?

2. **Grounding / retrieval doğruluğu**
  - cevap soruyla ilgili mi?
  - context gerçekten yeterli mi?
  - cevap context dışına taşıyor mu?
  - contradiction veya unsupported claim var mı?

3. **Ürün guardrail'leri**
  - konu dışı cevap yüksek skor almamalı
  - deflection yüksek skor almamalı
  - confirmed contradiction varsa skor sert biçimde bastırılmalı

Yani sistemin mantığı, tek bir LLM yargısına güvenmek değil; farklı risk boyutlarını ayrı ayrı ölçüp sonra ürün kurallarıyla birleştirmektir.

##### Neden tek bir overall judge kullanmıyoruz?

Çünkü tek çağrılık bir judge yaklaşımı pratikte şu sorunları üretir:

- neden düşük/yüksek skor verdiği yeterince açıklanamaz
- yazı kalitesi ile factual grounding birbirine karışır
- retrieval problemi ile answer-writing problemi ayrıştırılamaz
- debugging zorlaşır

Bu projede bunun yerine daha açıklanabilir bir tasarım seçilmiştir:

- rubric hattı, cevap kalitesini ölçer
- RAG analytical hattı, groundedness ve retrieval kalitesini ölçer
- final skor, deterministic ağırlıklar ve cap kurallarıyla üretilir

Bu yüzden sistemin ana amacı sadece “puan vermek” değildir; aynı zamanda **neden o puanı verdiğini operasyonel olarak anlamayı mümkün kılmaktır**.

##### Neden Stage 1 ve Stage 2 ayrı tutulmuş?

Rubric hattının kendi içinde de iki adıma ayrılması bilinçli bir tasarım kararıdır:

- `Stage 1`, rubric reasoning üretir
- `Stage 2`, bu reasoning'i strict JSON şemasına normalize eder

Buradaki fikir şudur: aynı anda hem serbest muhakeme hem de kusursuz şema uyumu istemek, tek çağrıda daha kırılgan davranış üretebilir. Bu yüzden sistem önce modelden kısa ama serbest rubric değerlendirmesi ister; ardından ikinci adımda bu metni zorunlu alanlara (`clarity`, `coherence`, `helpfulness`, `is_off_topic`, `is_deflection`, `overall_score`, `evaluation_confidence`, `reasoning_summary`) çevirir.

Bu ayrımın pratik faydaları:

- reasoning kalitesi ile output-format güvenliği ayrıştırılır
- JSON bozulursa yalnızca extraction / repair adımı tekrar denenir
- Stage 1 prompt'u rubric'e odaklanır; claim-level fact-checking yükü oraya bindirilmez
- daha ucuz ve daha yapılandırılmış ikinci model, normalization katmanı gibi çalışabilir

Dolayısıyla Stage 2 sadece “parser” değildir; serbest rubric muhakemesini üretim sisteminin beklediği şemaya güvenli biçimde indiren bir **normalization / repair layer** olarak düşünülebilir.

##### Bu tasarım hangi problemi çözüyor?

Bu mimari özellikle şu problem için uygundur:

- cevap akıcı ama yanlış olabilir
- cevap doğru parçalar içerebilir ama soruya tam hizmet etmeyebilir
- retrieval çok iyi olabilir ama son cevap kötü yazılmış olabilir
- model citation veriyor olabilir ama yanlış passage'a referans veriyor olabilir

Tek bir skor bu ayrımları kaybeder. Bu sistem ise bu failure mode'ları ayrıştırmayı hedefler.

##### Bu sistemin epistemolojisi nedir?

Teknik olarak sistem şu varsayımla kurulmuştur:

> “İyi bir cevap”, tek boyutlu bir kavram değildir.

İyi cevap için aynı anda birkaç şey gerekir:

- anlaşılır olmalı
- tutarlı olmalı
- kullanıcı işine yaramalı
- soruya ilgili olmalı
- mümkün olduğunca context ile desteklenmeli
- açık çelişki içermemeli

Dolayısıyla evaluation da çok eksenli yapılır. Bu yüzden `clarity` ile `hallucination_score` aynı metric değildir; `context_precision` ile `helpfulness` aynı problemi çözmez.

##### Neden deterministic kurallar eklenmiş?

Çünkü ürün seviyesi davranış tamamen serbest LLM yorumuna bırakılmak istenmemiştir.

Örnek ürün kararları:

- `is_deflection=True` ise skor cap'lenir
- `is_off_topic=True` ise skor cap'lenir
- `confirmed contradiction` varsa skor daha sert cap'lenir
- bazı durumlarda off-topic kararı LLM etiketinden bağımsız deterministic override ile verilir

Bu, sistemin sadece evaluator değil aynı zamanda **policy-enforced evaluator** olduğunu gösterir.

##### Bilinçli trade-off nedir?

Bu tasarımın açık trade-off'u şudur:

- **artı tarafı:** daha açıklanabilir, daha denetlenebilir, daha hata ayıklanabilir bir evaluation
- **eksi tarafı:** daha fazla LLM çağrısı, daha fazla latency, daha fazla cost

Yani mimari hız için değil, öncelikle kalite analizi ve failure-mode ayrıştırması için optimize edilmiştir.

##### En kısa ürün mantığı

Bu dokümana göre evaluation'i yapma mantığı şudur:

1. önce cevabın kullanıcı açısından kalitesini ölç
2. ayrı hatta cevap ile context arasındaki ilişkiyi ölç
3. retrieval kalitesini ayrı metriklerle ölç
4. riskli durumları guardrail ile bastır
5. bütün bunlardan açıklanabilir bir final skor üret

Bu nedenle bu doküman yalnızca “pipeline nasıl akıyor?” sorusunu değil, aynı zamanda “neden böyle akıyor?” sorusunu da cevaplamayı hedefler.

<a id="worked-example"></a>

#### 8.1.2 Worked Example

Bu bölüm, tek bir örnek trace üstünden sistemin nasıl düşündüğünü gösterir. Amaç gerçek kod akışını daha sezgisel hale getirmektir. Bu bölüm bilinçli olarak **niteliksel** tutulmuştur; ağırlık, normalizasyon ve cap hesabının sayısal karşılığı 8.1.7'de gösterilir.

##### Örnek trace

- `question`: "Redis ne işe yarar?"
- `contexts`:
  - `[0] Redis, in-memory key-value store'dur; sık kullanım alanları cache, session store, pub/sub ve leaderboard senaryolarıdır.`
  - `[1] Redis kalıcı depolama opsiyonları da sunabilir; fakat çoğu kullanımda çok hızlı erişim için kullanılır.`
- `answer`:
  - "Redis genelde cache için kullanılır. Session saklama ve pub/sub için de uygundur. Ayrıca ilişkisel veritabanı olarak uzun süreli finansal kayıt tutmak için idealdir."

##### Stage 1 bu cevabı nasıl okur?

Rubric hattı kabaca şu şekilde düşünür:

- cevap açık mı? → büyük ölçüde evet
- cevap tutarlı mı? → evet, yazı akışında bariz bozulma yok
- cevap yardımcı mı? → kısmen evet, çünkü kullanım alanlarını veriyor
- off-topic mi? → hayır
- deflection mı? → hayır

Yani yalnızca rubric açısından bakılırsa bu cevap orta-yüksek kalite görünebilir. Çünkü dilsel kalite ile groundedness aynı şey değildir.

##### RAG hattı bu cevabı nasıl okur?

RAG tarafı aynı cevabı farklı kırar:

- `answer_relevancy` yüksek olabilir, çünkü cevap soruyla ilgilidir
- `completeness` makul olabilir, çünkü cache / session / pub-sub gibi temel noktalar değinilmiştir
- ama `hallucination_score` düşebilir, çünkü “ilişkisel veritabanı olarak uzun süreli finansal kayıt tutmak için idealdir” ifadesi context tarafından açıkça desteklenmemektedir

Eğer hallucination claim analizi bu son cümleyi `unsupported claim` veya `confirmed contradiction` olarak işaretlerse final skor aşağı çekilir.

##### Final birleştirme neden önemlidir?

Bu örnek, sistemin neden iki ayrı hatta ihtiyaç duyduğunu gösterir:

- sadece rubric kullanılsaydı cevap olduğundan iyi görünebilirdi
- sadece hallucination kontrolü kullanılsaydı da yazı kalitesi ve kullanıcı faydası eksik okunabilirdi

Sistem bu iki bakışı birleştirerek daha dengeli karar vermeye çalışır.

##### Bu örnekten çıkarılacak ana ders

Bu sistemde iyi yazılmış bir cevap otomatik olarak yüksek skor almaz. Aynı şekilde sadece context'e yakın olmak da tek başına yeterli değildir. Nihai mantık şudur:

> Kullanıcıya yardımcı görünen ama grounding problemi taşıyan cevaplar ile grounding'i iyi ama kullanım kalitesi zayıf cevaplar birbirinden ayrıştırılmalıdır.

Bu bölümün amacı tam olarak bu zihinsel ayrımı göstermektir. Aynı örneğin ağırlıklı ortalama, `None`-skip normalizasyonu ve cap mekanikleriyle nasıl sayıya dönüştüğü ise 8.1.7'de ele alınır.

<a id="failure-mode-katalogu"></a>

#### 8.1.3 Failure Mode Kataloğu

Bu bölüm, sistemin özellikle hangi hata tiplerini ayırmaya çalıştığını açıklar.

##### 1. Akıcı ama halüsinasyonlu cevap

Özellikleri:

- `clarity` yüksek olabilir
- `coherence` yüksek olabilir
- `helpfulness` orta/yüksek olabilir
- ama `hallucination_score` ve/veya `faithfulness` düşer

Bu, sistemin yakalamak istediği en kritik failure mode'lardan biridir. Çünkü son kullanıcı açısından en tehlikeli cevap tipi çoğu zaman budur: **ikna edici ama yanlış cevap**.

##### 2. İlgili ama eksik cevap

Özellikleri:

- `answer_relevancy` yüksek olabilir
- `hallucination_score` da kötü olmayabilir
- ama `completeness` düşebilir

Bu, cevap doğru yönde olsa bile kullanıcı ihtiyacını tam kapatmadığını gösterir.

##### 3. Grounded ama yararsız cevap

Özellikleri:

- context'e sadık olabilir
- contradiction içermeyebilir
- ama `helpfulness` düşük olabilir
- bazen `clarity` / `coherence` de düşük olabilir

Bu failure mode, retrieval doğru olsa bile final UX'in kötü olabileceğini gösterir.

##### 4. Off-topic ama akıcı cevap

Özellikleri:

- yazı kalitesi yüzeyde iyi görünebilir
- fakat `answer_relevancy` düşer
- `helpfulness` de düşerse deterministic override ile `is_off_topic=True` set edilebilir

Bu yüzden sistem sadece judge boolean'ına değil, alt metrik kombinasyonuna da bakar.

##### 5. Citation var ama yanlış citation

Özellikleri:

- cevap kaynak göstermiş gibi görünür
- fakat `citation_check` düşer

Bu failure mode özellikle citation-first ürünlerde önemlidir; çünkü yalancı güven hissi üretir.

##### 6. Retriever çok şey getirmiş ama çoğu gereksiz

Özellikleri:

- `context_recall` makul olabilir
- ama `context_precision` düşük olabilir

Bu, bilgi eksikliğinden çok retrieval verimsizliği sorunudur.

##### 7. Retriever temiz ama yetersiz

Özellikleri:

- `context_precision` yüksek olabilir
- ama `context_recall` düşük olabilir

Bu da ters failure mode'dur: yanlış bilgi çok gelmiyordur, ama doğru bilgi de yeterince gelmiyordur.

##### 8. Deflection cevabı

Özellikleri:

- model kibar ve düzgün konuşabilir
- ama esasen "bilmiyorum / yardımcı olamam" der
- `is_deflection=True` olduğunda final skor cap'lenir

Bu, sistemin “nazik ama işe yaramaz” cevapları cezalandırmak istediğini gösterir.

<a id="metric-rationale"></a>

#### 8.1.4 Metric Rationale

Bu bölüm, her ana metriğin sistemde neden bulunduğunu ürün riski açısından açıklar.

##### `clarity`

Amaç: Kullanıcının cevabı anlayabilmesini ölçmek.

Neden gerekli?

- doğru bilgi anlaşılmaz yazılmışsa ürün değeri düşer

##### `coherence`

Amaç: Cevabın iç mantık akışını ve çelişkisizliğini ölçmek.

Neden gerekli?

- birbirini bozan ifadeler güven kaybı yaratır

##### `helpfulness`

Amaç: Cevabın gerçekten kullanıcı amacına hizmet edip etmediğini ölçmek.

Neden gerekli?

- doğru ama işe yaramayan cevaplar ürün açısından zayıftır

##### `answer_relevancy`

Amaç: Cevabın soruya ne kadar bağlı kaldığını ölçmek.

Neden gerekli?

- model bazen doğru görünen ama sorunun merkezine hizmet etmeyen içerik üretebilir

##### `hallucination_score` / `faithfulness`

Amaç: Cevabın context ile ne kadar desteklendiğini ölçmek.

Neden gerekli?

- RAG sistemlerinde en kritik risk, akıcı ama context dışı bilgi üretimidir

##### `completeness`

Amaç: Kullanıcının bilgi ihtiyacının ne kadar kapandığını ölçmek.

Neden gerekli?

- cevap doğru olabilir ama eksik kaldığında yine kullanıcı problemi çözülmez

##### `context_precision`

Amaç: Retriever'ın getirdiği context'lerin ne kadarının gerçekten yararlı olduğunu ölçmek.

Neden gerekli?

- çok fazla gürültü downstream answer kalitesini bozar

##### `context_recall`

Amaç: Gerekli bilginin context içinde bulunup bulunmadığını ölçmek.

Neden gerekli?

- retriever doğru bilgiyi hiç getirmediyse answer modelini tek başına suçlamak adil değildir

##### `citation_check`

Amaç: Cevapta verilen kaynak referanslarının gerçekten doğru passage'a işaret edip etmediğini ölçmek.

Neden gerekli?

- kaynak gösteren ama yanlış referans veren cevaplar sahte güven üretir

##### `is_off_topic` ve `is_deflection`

Amaç: Ürün açısından kabul edilemez cevap tiplerini ayrı guardrail olarak işaretlemek.

Neden gerekli?

- bazı failure mode'lar sadece numeric ortalamaya bırakılmamalıdır

##### Metrikler gerçekten bağımsız mı?

Hayır. Bu sistemde metrikler bilinçli olarak ayrı hesaplanır; fakat istatistiksel olarak tamamen bağımsız oldukları varsayılmaz.

Özellikle şu örtüşmeler önemlidir:

- `hallucination_score` ile `faithfulness`, aynı `hallucination_claims` listesinden türetilir; biri toplam ceza şiddetini, diğeri problemli claim sayısını yansıtır
- `context_precision` ile `context_recall`, retrieval'ın iki kardeş sinyalidir; biri gürültüyü, diğeri eksikliği ölçer
- `completeness` ile `context_recall`, gerekli bilgi retrieval tarafından hiç getirilmediğinde birlikte düşebilir
- `answer_relevancy` ile `helpfulness`, özellikle konu dışı veya yüzeysel cevaplarda birbirini etkileyebilir; hatta bazı durumlarda deterministic off-topic override bu iki sinyali birlikte kullanır
- `citation_check`, seyrek ve koşullu bir metriktir; answer'da citation deseni yoksa bu metric çoğu durumda uygulanamaz kabul edilir

Dolayısıyla bu evaluation sistemi, “bağımsız metriklerin saf toplamı” gibi okunmamalıdır. Mevcut scorer korelasyon düzeltmesi veya covariance tabanlı bir de-correlation yapmaz; bunun yerine manuel ağırlıklar ile örtüşmeyi kısmen dengelemeye çalışır.

##### Sonuç

Bu metrik seti rastgele seçilmiş bir skor listesi değildir. Her biri farklı bir üretim riskine karşılık gelir. Sistem mantığı da tam burada yatar: **tek skor değil, risk ayrıştırması yapan bir evaluation yapısı kurmak.**

> **Çapraz referans:** Her metriğin prompt mantığı ve skorlama formülü [Section 9.1](#91-metriklerin-teknik-analizi)'de; FP/FN beklentileri [8.1.6](#false-positive-false-negative-beklentileri)'da yer alır.

<a id="weight-cap-rationale"></a>

#### 8.1.5 Weight & Cap Rationale

Bu bölüm önemli bir sınıra sahiptir: kod içinde bu ağırlıkların ve cap değerlerinin neden seçildiğine dair tarihsel deney notu veya ADR kaydı bulunmamaktadır. Bu nedenle aşağıdaki açıklama, mevcut implementasyondan okunabilen **ürün mantığı**dır; tarihsel karar kaydı değildir.

##### Ağırlıklar neden böyle görünüyor?

Mevcut dağılım şu eğilimi gösterir:

- `hallucination_score` + `faithfulness` + `answer_relevancy` + `context_precision` + `context_recall` + `completeness`
  birlikte grounding / retrieval tarafına baskın etki verir
- `helpfulness`, kullanıcı değerini güçlü şekilde oyuna sokar
- `clarity` ve `coherence`, önemlidir ama tek başına dominant değildir
- `citation_check`, özel ama ikincil bir güven metriği olarak tutulur

Bu, tasarımın şu prensibe göre kurulduğunu düşündürür:

> Cevap sadece iyi yazılmış diye yüksek skor almamalı; ama sadece teknik olarak grounded diye de kullanıcı açısından iyi kabul edilmemeli.

Yani ağırlıklar, iki uç yaklaşım arasında denge kurar:

- salt writing-quality judge
- salt factual-grounding judge

##### Neden `helpfulness` görece yüksek?

Çünkü ürün seviyesi başarı tanımı yalnızca doğruluk değildir. Kullanıcının işini çözen cevap ile sadece teknik olarak zararsız cevap aynı kabul edilmemiştir.

Bu yüzden `helpfulness` yüksek tutulmuştur; aksi halde sistem retrieval backend gibi davranır, answer quality backend gibi değil.

##### Neden `clarity` ve `coherence` daha düşük?

Çünkü bu iki metrik önemlidir ama tek başına güvenlik veya doğruluk sağlamaz.

Örnek:

- çok açık yazılmış bir cevap yanlış olabilir
- çok akıcı bir cevap halüsinasyon içerebilir

Bu nedenle bu metrikler ürün kalitesine katkı verir; fakat final skorun omurgasını oluşturmaz.

##### Neden `0.20` deflection / off-topic cap'i seçilmiş olabilir?

Kodun ürüne verdiği mesaj şudur:

- off-topic cevap neredeyse başarısız kabul edilir
- deflection cevabı da neredeyse başarısız kabul edilir
- ama skor tamamen `0.0`'a zorlanmaz

Bu yüzden `0.20` değeri, “çok düşük ama mutlak sıfır olmayan” bir ceza bölgesi gibi davranır. Yani ürün şu mesajı verir:

> Bu cevap kabul edilebilir başarı sayılmaz; en fazla çok düşük kaliteli bir sonuç olarak görülebilir.

##### Neden `0.35` contradiction cap'i seçilmiş olabilir?

`confirmed contradiction`, basit eksiklikten daha ağır, fakat her durumda tam off-topic / tam deflection kadar yapısal olmayan bir hata gibi ele alınmıştır.

Bu yüzden `0.35` değeri şuna benzer bir ürün kararıdır:

- cevapta bazı iyi parçalar olabilir
- ama açık çelişki olduğu için yüksek skor kesinlikle verilmemeli

Yani contradiction, “ciddi güven problemi” olarak ele alınır; fakat her durumda otomatik sıfırlama yapılmaz.

##### Bu değerler ne anlama gelmiyor?

Bu değerler şunları garanti etmez:

- evrensel olarak en iyi threshold'lar olduklarını
- tüm domain'lerde optimal olduklarını
- istatistiksel kalibrasyonlarının tamamlandığını

##### Ne zaman yeniden kalibre edilmeli?

Mevcut kod bu kararı otomatik veren bir calibration loop içermez. Ancak operasyonel olarak şu sinyaller görüldüğünde ağırlıklar veya cap değerleri yeniden gözden geçirilmelidir:

- aynı trace'lerde tekrar çalıştırmalarda metric oynaklığı belirginse
- labeled set üstünde metric ile insan etiketi korelasyonu zayıflıyorsa
- iyi / orta / kötü bucket'ları ayırma gücü düşüyorsa
- aynı kanıttan beslenen iki metric composite skoru gereğinden fazla domine ediyorsa
- `is_deflection`, `is_off_topic` veya `confirmed contradiction` içeren örnekler ürün beklentisine göre hâlâ fazla yüksek skor alıyorsa

Bu nedenle gelecekteki kalibrasyon tartışması için en makul soru “bu sayı tarihsel olarak neden seçildi?” değil, “bu sayı bugünkü labeled set ve regression trace davranışını hâlâ doğru temsil ediyor mu?” sorusudur.

Dolayısıyla bu bölümün teknik sonucu şudur:

> Ağırlıklar ve cap'ler, bugünkü ürün davranışını temsil eder; ileride benchmark ve labeled set sonuçlarına göre yeniden kalibre edilebilir.

> **Çapraz referans:** Ağırlık ve cap değerlerinin tam kod karşılığı için [Section 10](#10-overall-score-hesabı)'a; uçtan uca sayısal örnek için [8.1.7](#numeric-end-to-end-example)'ye bakınız.

<a id="false-positive-false-negative-beklentileri"></a>

#### 8.1.6 False Positive / False Negative Beklentileri

Bu bölümde yazılanlar gözlemsel üretim raporu değil, mevcut prompt ve metric tasarımına bakarak beklenebilecek hata eğilimleridir.

##### `clarity`

- olası false positive: çok akıcı ama içerik olarak boş cevapların açık kabul edilmesi
- olası false negative: teknik ama yoğun cevapların gereğinden düşük açıklık alması

##### `coherence`

- olası false positive: mantıksal akışı düzgün ama faktüel olarak yanlış cevapların yüksek kalması
- olası false negative: kısa, maddelemeli veya telegraphic cevapların olduğundan kopuk görünmesi

##### `helpfulness`

- olası false positive: kullanıcıya güven veren ama aslında eksik cevapların faydalı sayılması
- olası false negative: kısa ama doğru cevapların yetersiz görülmesi

##### `answer_relevancy`

- olası false positive: soruyla ilgili görünen ama gereksiz yan bilgilerin relevant sayılması
- olası false negative: dolaylı ama yine de işe yarayan bağlamsal cümlelerin irrelevant sayılması

##### `hallucination_score` / `faithfulness`

- olası false positive: context ile gevşek uyumlu paraphrase'lerin fazla hoşgörü ile desteklenmiş sayılması
- olası false negative: doğru ama context'te birebir yazmayan makul çıkarımların unsupported gibi görünmesi

Bu ikili özellikle domain bağımlıdır; context kalitesi ve passage parçalanması sonucu ciddi etkiler.

##### `completeness`

- olası false positive: key point çıkarımı dar yapıldıysa eksik cevap olduğundan daha tamam görünür
- olası false negative: model gereğinden fazla veya fazla ince ayrıntılı key point çıkarırsa skor düşebilir

##### `context_precision`

- olası false positive: genel arka plan passage'ları gerçekten gerekliymiş gibi relevant işaretlenebilir
- olası false negative: dolaylı ama yararlı passage'lar irrelevant sayılabilir

##### `context_recall`

- olası false positive: context'te ima edilen ama tam taşınmayan bilgi “found” sayılabilir
- olası false negative: bilgi birkaç passage'a dağılmışsa model bunları birleştiremeyip “not_found” diyebilir

##### `citation_check`

- olası false positive: pasaj kısmen destekliyorsa citation gereğinden rahat doğru sayılabilir
- olası false negative: citation formatı standart dışıysa veya referans dolaylıysa yanlış sayılabilir

##### `is_off_topic`

- olası false positive: çok kısa ama alakalı cevaplar düşük `helpfulness` + düşük `answer_relevancy` nedeniyle override ile off-topic'e çekilebilir
- olası false negative: cevabın yüzeysel ilgili görünmesi nedeniyle gerçekte konu dışı içerik kaçabilir

##### `is_deflection`

- olası false positive: güvenli cevap veren ama kısmen yararlı açıklama içeren yanıtlar deflection gibi okunabilir
- olası false negative: model dolaylı kaçamak dil kullanıp açıkça “bilmiyorum” demeden sorudan kaçabilir

##### Genel sonuç

Bu metric seti güçlüdür ama kusursuz değildir. Teknik ekip, metrikleri mutlak gerçek olarak değil, **hata eğilimleri bilinen sinyaller** olarak okumalıdır.

<a id="numeric-end-to-end-example"></a>

#### 8.1.7 Numeric End-to-End Example

Bu bölüm, worked example mantığını sayısal hale getirir.

Burada önemli bir normalizasyon detayı vardır: `_OVERALL_WEIGHTS` toplamı `1.00` olsa da scorer, değeri `None` olan metric'leri paydaya katmaz. `citation_check` metriğinin ağırlığı `0.05`'tir; answer içinde citation deseni yoksa bu metric çoğu durumda “başarısız” değil, **uygulanamaz** kabul edilir ve `None` döner. Bu nedenle aşağıdaki iki senaryoda `citation_check=None` olduğu için normalize denominator `1.00 - 0.05 = 0.95` olur.

##### Senaryo A — iyi yazılmış ama grounded değil

Varsayalım aşağıdaki skorlar oluştu:

- `clarity = 0.90`
- `coherence = 0.85`
- `helpfulness = 0.80`
- `answer_relevancy = 0.95`
- `completeness = 0.75`
- `context_precision = 0.80`
- `context_recall = 0.80`
- `hallucination_score = 0.35`
- `faithfulness = 0.40`
- `citation_check = None`

Burada `citation_check` uygulanmadığı için o metrik hem paydan hem de paydadan çıkarılır. Normalize weighted average yaklaşık şöyle olur:

$$
\frac{(0.35 \times 0.15) + (0.40 \times 0.10) + (0.95 \times 0.15) + (0.75 \times 0.10) + (0.80 \times 0.10) + (0.80 \times 0.10) + (0.80 \times 0.15) + (0.85 \times 0.05) + (0.90 \times 0.05)}{0.95}
= 0.7132
$$

Ama hallucination claim'leri içinde `confirmed contradiction` varsa cap uygulanır:

$$
final\_score = \min(0.7132, 0.35) = 0.35
$$

Bu örnek, sistemin neden sadece yazı kalitesine bakmadığını net gösterir.

##### Senaryo B — grounded ama yararsız

Varsayalım aşağıdaki skorlar oluştu:

- `clarity = 0.50`
- `coherence = 0.45`
- `helpfulness = 0.25`
- `answer_relevancy = 0.65`
- `completeness = 0.40`
- `context_precision = 0.90`
- `context_recall = 0.90`
- `hallucination_score = 0.95`
- `faithfulness = 0.95`
- `citation_check = None`

Bu durumda da aynı nedenle denominator `0.95` kalır. Normalize weighted average yaklaşık:

$$
\frac{(0.95 \times 0.15) + (0.95 \times 0.10) + (0.65 \times 0.15) + (0.40 \times 0.10) + (0.90 \times 0.10) + (0.90 \times 0.10) + (0.25 \times 0.15) + (0.45 \times 0.05) + (0.50 \times 0.05)}{0.95}
= 0.6737
$$

Bu sonuç ilginçtir: cevap grounding açısından güçlüdür ama final kullanıcı değeri orta seviyede kalır. Yani sistem “doğru ama kötü UX” vakasını da ayırır.

##### Senaryo C — deflection

Varsayalım bazı metrikler orta görünse bile `is_deflection=True` olsun. Örneğin normalize skor `0.62` çıksın.

Cap sonrası:

$$
final\_score = \min(0.62, 0.20) = 0.20
$$

Bu da ürün politikasını açıklar: nazik veya düzgün yazılmış bir kaçamak cevap, yüksek başarı sayılmaz.

##### Bu sayısal örneklerden çıkarım

Bu sistemin final skoru şu tür bir mantık taşır:

- writing quality tek başına yetmez
- grounding tek başına yetmez
- riskli failure mode'lar cap ile bastırılır
- final skor, metriklerin ham toplamı değil, ürün politikasıyla şekillenen bir birleşik sinyaldir


### 8.2 Stage 1 — rubric reasoning

Model: `settings.stage_1_model` (varsayılan `gpt-5.2`)

Stage 1'in görevi serbest metin rubric reasoning üretmektir. Neden ayrı bir aşama olarak var olduğu 8.1.1'de ("Neden Stage 1 ve Stage 2 ayrı tutulmuş?") açıklanmıştır.

Girdiler: `question`, `answer`, `contexts` (opsiyonel `ground_truth` bu aşamada kullanılmaz).

#### Prompt yapısı

System prompt modele rubrice odaklanmasını söyler ve claim-level fact checking'i açıkça yasaklar:

```python
STAGE_1_SYSTEM_PROMPT = """
You are an expert RAG answer quality evaluator.
Strictly follow the rubric below when scoring.
For each metric, write brief but clear reasoning (2-3 sentences max per metric).
Keep total output under 1500 words.
Use the anchor values (1.0 / 0.7 / 0.4 / 0.0) as reference points when scoring.
Do NOT perform claim-level fact-checking — that is handled by a separate analytical pipeline.
Focus only on the rubric dimensions listed.
""".strip()
```

User prompt'u rubric bloğu, soru, cevap ve context'leri tek mesajda birleştirir:

```python
def build_stage_1_user_prompt(question, answer, contexts):
    # truncation uygulanır
    return (
        f"{RUBRIC_BLOCK}\n\n"
        f"Question:\n{question}\n\n"
        f"Answer:\n{answer}\n\n"
        f"Contexts:\n{context_block}\n\n"
        "For each rubric metric, write brief reasoning and propose a score."
    )
```

#### Değerlendirilen boyutlar

Rubric tanımı (`RUBRIC_BLOCK`) şu boyutları kapsar:

- `clarity` (0.0–1.0): cevabın okunabilirliği
- `coherence` (0.0–1.0): iç mantık akışı
- `helpfulness` (0.0–1.0): kullanıcı fayda düzeyi
- `is_off_topic` (boolean): soruyla hiç ilgisiz mi
- `is_deflection` (boolean): bilmiyorum/kaçamak cevap mı

Her boyut için 4 anchor değeri tanımlanmıştır (1.0 / 0.7 / 0.4 / 0.0).

#### Çağrı

```python
async def _run_stage_1(client, question, answer, context_items):
    return await client.chat_completion(
        model=settings.stage_1_model,
        system_prompt=STAGE_1_SYSTEM_PROMPT,
        user_prompt=build_stage_1_user_prompt(question, answer, context_items),
        max_completion_tokens=4096,
    )
```

Bu aşama JSON değil, serbest metin reasoning üretir. Output bütçesi (`4096` token) gerçek muhakeme üretimi içindir.

##### Stage 1 output word limit

System prompt LLM'e `"Keep total output under 1500 words"` talimatı verir. Bu, rubric reasoning'in gereksiz uzamasını ve token maliyetini sınırlar.

##### Input truncation davranışı

Prompt'a girmeden önce tüm input'lar konfigüre edilebilir limitlerle kırpılır:

- Kırpılan metin sonuna `\n...[truncated]` marker eklenir — LLM kırpılma olduğunu görür
- Her context ayrı ayrı `MAX_SINGLE_CONTEXT_CHARS` ile sınırlanır
- Toplam context bütçesi `MAX_CONTEXT_TOTAL_CHARS` ile sınırlanır
- Bütçe tükendiğinde kalan context'ler **tamamen düşürülür** (kısmi ekleme yapılmaz)
- `question` ve `answer` da ayrı limitlerle kırpılır (`MAX_QUESTION_CHARS`, `MAX_ANSWER_CHARS`)

Bu limitler `app/config.py` içinde environment variable olarak override edilebilir.

Kaynak: [app/evaluation/prompts.py](app/evaluation/prompts.py), [app/evaluation/evaluator.py](app/evaluation/evaluator.py), [app/evaluation/prompt_utils.py](app/evaluation/prompt_utils.py)

### 8.3 Stage 2 — JSON extraction

Model: `settings.stage_2_model` (varsayılan `gpt-4o-mini`)

Stage 2 bir "judge" değildir; Stage 1 reasoning çıktısını strict JSON şemasına dönüştüren bir **normalization / repair layer**'dır.

#### Strict JSON schema

```python
STAGE_2_JSON_SCHEMA = {
    "name": "evaluation_result",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "clarity": {"type": "number"},
            "is_off_topic": {"type": "boolean"},
            "coherence": {"type": "number"},
            "helpfulness": {"type": "number"},
            "is_deflection": {"type": "boolean"},
            "overall_score": {"type": "number"},
            "evaluation_confidence": {"type": "number"},
            "reasoning_summary": {"type": "string"},
        },
        "required": ["clarity", "is_off_topic", "coherence", "helpfulness",
                      "is_deflection", "overall_score", "evaluation_confidence",
                      "reasoning_summary"],
        "additionalProperties": False,
    },
}
```

#### Retry ve repair mekanizması

```python
async def _run_stage_2_with_retries(client, stage_1_content):
    for attempt in range(_MAX_STAGE_2_RETRIES):
        if attempt == 0:
            s2_resp = await client.chat_completion(
                model=settings.stage_2_model,
                system_prompt=STAGE_2_SYSTEM_PROMPT,          # "You are a JSON converter assistant."
                user_prompt=build_stage_2_user_prompt(stage_1_content),
                max_completion_tokens=2048,
                json_schema=STAGE_2_JSON_SCHEMA,
            )
        else:
            s2_resp = await client.chat_completion(
                model=settings.stage_2_model,
                system_prompt=STAGE_2_REPAIR_SYSTEM_PROMPT,    # "You are a JSON repair assistant."
                user_prompt=build_stage_2_repair_user_prompt(
                    last_output, stage_1_content, validation_errors,
                ),
                max_completion_tokens=2048,
                json_schema=STAGE_2_JSON_SCHEMA,
            )
        # validation, break on success
    else:
        # regex fallback
```

Safety katmanları sırayla: strict schema → retry with repair prompt → regex fallback.

Maksimum deneme sayısı: `_MAX_STAGE_2_RETRIES = 3` (1 ilk deneme + 2 repair denemesi). Tüm denemeler başarısız olursa regex fallback'e geçilir.

##### Repair reasoning truncation

Repair retry'larda orijinal Stage 1 reasoning metni **4000 karakter** ile sert kırpılır. Bu limit konfigüre edilemez. Amaç: uzun reasoning'in repair prompt'unu şişirip model context window'unu tüketmesini önlemektir.

##### JSON parsing stratejisi

LLM çıktısından JSON çıkarmak için üç strateji sırayla denenir:

1. **Outermost `{…}` slice** — ilk `{` ile son `}` arasındaki substring parse edilir
2. **Markdown fence strip** — ` ```json ... ``` ` bloğu varsa iç kısım alınır
3. **Raw content** — ham metin doğrudan parse denenir

İlk başarılı parse kabul edilir. Hiçbiri çalışmazsa fallback dict döner (`{"reasoning_summary": "Stage 2 JSON parse failed"}`).

##### Type coercion

JSON parse sonrası tüm değerlere savunma dönüşümü uygulanır:

- Float alanlar (`clarity`, `coherence`, `helpfulness`, `overall_score`, `evaluation_confidence`) `[0.0, 1.0]` aralığına clamp edilir
- String boolean'lar dönüştürülür: `"true"`, `"1"`, `"yes"`, `"evet"` → `True`; diğer değerler → `False`

##### Regex fallback

Stage 2 tüm retry'lardan sonra da başarısız olursa son çare olarak Stage 1 CoT metninden regex ile skor çıkartılır:

- `CLARITY: 0.7`, `clarity = 0.7` gibi pattern'ler aranır
- Boolean alanlar Türkçe desteği içerir: `evet`/`hayir` → `True`/`False`
- `overall_score`, bulunan float skorların **basit ortalaması** olarak hesaplanır (ağırlıklı formül değil)
- `evaluation_confidence`, bulunan skor sayısı / toplam float alan sayısı olarak set edilir — LLM güvenliği değil extraction completeness ölçüsüdür

Bu fallback normal akışta çalışmaz; yalnızca tüm JSON parse yolları tükendiğinde devreye girer.

Kaynak: [app/evaluation/prompts.py](app/evaluation/prompts.py), [app/evaluation/evaluator.py](app/evaluation/evaluator.py), [app/evaluation/json_utils.py](app/evaluation/json_utils.py)

### 8.4 RAG metrics pipeline

Model: `settings.rag_metrics_model` (varsayılan `gpt-5-mini`)

6 analytical metrik paralel `asyncio.create_task` ile başlatılır:

```python
async def compute_rag_metrics(question, answer, contexts, ground_truth, client):
    relevancy_task     = asyncio.create_task(compute_answer_relevancy(client, question, answer, ctx))
    citation_task      = asyncio.create_task(compute_citation_check(client, answer, ctx))
    hallucination_task = asyncio.create_task(compute_hallucination_rubric(client, answer, ctx))
    completeness_task  = asyncio.create_task(compute_completeness(client, question, answer, ctx))
    ctx_precision_task = asyncio.create_task(compute_context_precision(client, question, ctx))
    ctx_recall_task    = asyncio.create_task(compute_context_recall(client, question, ctx, ground_truth))
    # await all, merge results
```

Üretilen metrikler:

| Metrik | Kaynak | Not |
|---|---|---|
| `answer_relevancy` | statement-level decomposition | soruyla ilgililik |
| `hallucination_score` | claim extraction + context comparison | context uyumu |
| `faithfulness` | aynı claim listesinden türetilir | claim-bazlı sadakat |
| `citation_check` | citation pattern varsa çalışır | yoksa `None` |
| `completeness` | key point extraction + coverage | kapsamlılık |
| `context_precision` | passage-level relevancy | retrieval gürültüsü |
| `context_recall` | information need coverage | retrieval eksikliği |

Notlar:

- `citation_check`, cevapta citation deseni yoksa `None` olur (uygulanamaz, başarısız değil).
- `ground_truth`, özellikle `context_recall` için kullanılır.
- Her metriğin prompt ve formül detayı Section 9.1'de; metrikler arası bağımlılık ve overlap tartışması 8.1.4'te yer alır.

Kaynak: [app/evaluation/rag_metrics.py](app/evaluation/rag_metrics.py), [app/evaluation/prompts.py](app/evaluation/prompts.py)

##### LLM çıktı token bütçeleri

Her LLM çağrısının hardcoded `max_completion_tokens` değeri vardır:

| Aşama | `max_completion_tokens` | Not |
|---|---|---|
| Stage 1 | `4096` | Serbest rubric reasoning |
| Stage 2 (initial + repair) | `2048` | JSON extraction |
| Hallucination | `4096` | Claim listesi uzun olabilir |
| Citation check | `1536` | Daha kısa çıktı yeterli |
| Diğer RAG metrikleri | `2048` | answer_relevancy, completeness, context_precision, context_recall |

Bu değerler konfigüre edilemez. Stage 1'in yüksek bütçesi serbest muhakeme için gereklidir; diğer aşamalar daha yapılandırılmış çıktı ürettiği için düşük tutulmuştur.

### 8.5 Hata davranışı

Sistem tamamen kırılmak yerine tutarlı bir boş/fallback payload üretir:

```python
def _build_empty_result(*, reasoning_summary, raw_response):
    return {
        "clarity": None, "is_off_topic": None, "completeness": None,
        "coherence": None, "helpfulness": None, "is_deflection": None,
        "overall_score": None, "evaluation_confidence": None,
        "reasoning_summary": reasoning_summary, ...
    }
```

Fallback tetikleyicileri:

- API key yoksa → evaluation skip
- Stage 2 parse başarısızsa → retry → repair prompt → regex fallback
- LLM client hatasında → boş ama tutarlı response contract

Bu sayede downstream tüketici her durumda aynı şemayı görür.

Kaynak: [app/evaluation/evaluator.py](app/evaluation/evaluator.py)

### 8.6 Operasyonel akış özeti

Tek bir trace için çalışma sırası:

1. trace DB'den yüklenir
2. input'lerden `content_hash` üretilir
3. aynı input daha önce evaluate edilmişse cache hit → sonuç kopyalanır
4. cache miss ise `evaluate_trace()` çağrılır
5. Stage 1 rubric reasoning ve RAG metrics **aynı anda** başlatılır
6. Stage 1 bitince Stage 2 JSON extraction çalışır
7. Stage 2 sonucu ile RAG sonuçları merge edilir
8. weighted `overall_score` hesaplanır (detay: Section 10)
9. sonuç DB'ye yazılır
10. trace multi-agent ise step evaluation'lar ayrıca çalışır (detay: Section 11)
11. webhook varsa callback gönderilir (detay: Section 12)

Cache notu: `content_hash`, `question + answer + contexts + ground_truth` üstünden üretilir. Gelecekte evaluation profili veya model varyantı eklenirse cache key tasarımı yeniden düşünülmelidir.

### 8.7 Teknik değerlendirme özeti

##### Güçlü yönler
- rubric + analytical hybrid tasarım
- parallel RAG metrics (latency: toplam → maks'a düşer)
- weighted deterministic overall score
- content-hash cache
- webhook ve async destek
- multi-agent pipeline görünürlüğü

##### Zayıf yönler / maliyet alanları
- Stage 1 + Stage 2 → iki ayrı LLM çağrısı
- 6 paralel RAG çağrısı → vendor rate-limit riski
- multi-agent step eval → maliyet çarpanı
- latency büyük ölçüde vendor inference süresine bağlı

##### İyileştirme adayları
- Stage 1 + Stage 2'yi tek structured output çağrısına indirgemek
- bazı RAG metric'leri tek çağrıda birleştirmek
- profile-based evaluation (`fast / standard / audit`)
- metric-level cache
- step evaluation'ı koşullu çalıştırmak


## 9. Metrikler

Sistemin kullanıcıya sunduğu ana skorlar şunlardır:

### Rubric kökenli skorlar
- `clarity`
- `coherence`
- `helpfulness`

### RAG / analytical skorlar
- `completeness`
- `answer_relevancy`
- `context_precision`
- `context_recall`
- `faithfulness`
- `hallucination_score`
- `citation_check`

### Bayraklar
- `is_off_topic`
- `is_deflection`

### Üst skor
- `overall_score`

### Detay alanları
- `hallucination_claims`
- `completeness_key_points`
- `reasoning_summary`
- `evaluation_commentary`

### 9.1 Metriklerin teknik analizi

Bu bölümde metrikler sadece isim olarak değil, **hangi prompt mantığıyla** ve **hangi skorlama formülüyle** üretildikleri açısından açıklanır.

> **Çapraz referans:** Her metriğin *neden* bulunduğuna dair ürün riski açıklaması [8.1.4 Metric Rationale](#metric-rationale)'de; FP/FN beklentileri [8.1.6](#false-positive-false-negative-beklentileri)'da yer alır.

#### A. `clarity`, `coherence`, `helpfulness`

Bu üç skor rubric hattından gelir. Yani bunlar [app/evaluation/prompts.py](app/evaluation/prompts.py) içindeki `RUBRIC_BLOCK` ve `STAGE_1_SYSTEM_PROMPT` ile üretilir; daha sonra [app/evaluation/evaluator.py](app/evaluation/evaluator.py) içindeki Stage 2 ile JSON alana dönüştürülür.

Rubric tanımından ilgili bölüm:

```python
CLARITY (of the ANSWER):
- 1.0 = Answer is clear, well-structured, easy to understand, no contradictions.
- 0.7 = Generally understandable, minor ambiguity or slight redundancy.
- 0.4 = Convoluted, hard to follow, contains contradictory statements, or uses excessive hedging.
- 0.0 = Nonsensical, unparseable, or riddled with contradictions.

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
```

Bu skorların doğası gereği:

- daha çok **cevabın yazım ve kullanıcı faydası kalitesini** ölçer
- retrieval doğruluğunu doğrudan ölçmez
- context'e dayanıyor olsa da claim-by-claim evidence verification yapmaz

Teknik yorum:

- güçlü yön: kullanıcı deneyimi kalitesini yakalar
- zayıf yön: cevap akıcı ama yanlışsa tek başına yeterli güvence sağlamaz

#### B. `is_off_topic` ve `is_deflection`

Bu iki alan da rubric hattından gelir ve binary flag olarak üretilir.

Prompt tanımı:

```python
IS_OFF_TOPIC:
- true  = The ANSWER does not address the question at all; it discusses an entirely unrelated topic.
- false = The ANSWER makes a genuine attempt to address the question, even if partially or incorrectly.

IS_DEFLECTION:
- true  = Contains deflection ("I don't know", "I can't help") with no substantive information.
- false = Genuine attempt to answer with content.
```

Bu flag'ler sadece görünür verdict değildir; [SYSTEM_DOCUMENTATION.md](SYSTEM_DOCUMENTATION.md) içinde yukarıda anlatıldığı gibi final `overall_score` üstünde cap uygular.

Bu nedenle bunlar ürün davranışı açısından yüksek etkili guardrail alanlarıdır.

#### C. `answer_relevancy`

Bu metrik [app/evaluation/rag_metrics.py](app/evaluation/rag_metrics.py) içinde statement-level decomposition ile hesaplanır. İlgili fonksiyon mantığı şöyledir:

```python
async def compute_answer_relevancy(
  client: LLMChatClient,
  question: str,
  answer: str,
  contexts: list[str],
) -> float | None:
  resp = await client.chat_completion(
    model=settings.rag_metrics_model,
    system_prompt=ANSWER_RELEVANCY_SYSTEM_PROMPT,
    user_prompt=build_answer_relevancy_user_prompt(question, answer),
    max_completion_tokens=2048,
    json_schema=ANSWER_RELEVANCY_JSON_SCHEMA,
  )

  parsed = _safe_parse(resp.content)
  statements = parsed.get("statements", [])
  relevant_count = sum(
    1 for s in statements if isinstance(s, dict) and s.get("relevant") is True
  )
  total = len(statements)
  score = round(relevant_count / total, 4) if total > 0 else None
```

Prompt mantığı:

```python
ANSWER_RELEVANCY_SYSTEM_PROMPT = """
You are an answer relevancy evaluation expert. Your task:
1. Decompose the given answer into individual statements.
2. For each statement, determine whether it is RELEVANT to the user's question.
...
""".strip()
```

Bu metrik şunu ölçer:

- cevap içindeki cümlelerin ne kadarı soruyla ilgili?

Şunu ölçmez:

- o cümleler doğru mu?
- context tarafından destekleniyor mu?

Yani `answer_relevancy` yüksek olup `hallucination_score` düşük olabilir.

#### D. `hallucination_score` ve `faithfulness`

Bu iki skor aynı hallucination pipeline'ından türetilir. Bu hat [app/evaluation/prompts.py](app/evaluation/prompts.py) içindeki prompt ile atomic claim extraction + context comparison yapar:

```python
HALLUCINATION_SYSTEM_PROMPT = """
You are a hallucination detection evaluator.

Task:
1. Extract atomic factual claims from the ANSWER.
2. For each claim, compare against CONTEXT PASSAGES.
3. Label each claim with one disagreement_type:
   - "agreement"
   - "unsupported claim"
   - "confirmed contradiction"
""".strip()
```

Runtime tarafında ilgili çağrı:

```python
async def compute_hallucination_rubric(
  client: LLMChatClient,
  answer: str,
  contexts: list[str],
) -> dict[str, Any]:
  resp = await client.chat_completion(
    model=settings.rag_metrics_model,
    system_prompt=HALLUCINATION_SYSTEM_PROMPT,
    user_prompt=build_hallucination_user_prompt(answer, contexts),
    max_completion_tokens=4096,
    json_schema=HALLUCINATION_JSON_SCHEMA,
  )
```

Bu hattın çıktısı claim listesi üretir; sonra skor türetilir.

Teknik yorum:

- `hallucination_score`: answer'ın context ile ne kadar uyumlu olduğunu özetleyen skor
- `faithfulness`: answer'ın context'e sadakatini ayrı eksende yansıtan skor
- `hallucination_claims`: hangi claim'lerde sorun bulunduğunu açıklayan detay alanı

##### Neden `faithfulness` ayrı bir skor?

Bu iki skor bilinçli olarak ayrı tutulur; çünkü aynı claim listesine bakmalarına rağmen farklı sinyal üretirler:

- `hallucination_score`, hata **şiddetini** ölçer; `confirmed contradiction`, `unsupported claim`'den daha ağır cezalandırılır
- `faithfulness`, hata **yaygınlığını** ölçer; problemli claim sayısı arttıkça lineer biçimde düşer

Dolayısıyla `hallucination_score` daha çok “cevapta ne kadar ağır grounding problemi var?” sorusunu, `faithfulness` ise “cevabın ne kadarı context'e sadık kaldı?” sorusunu cevaplar. Bu ayrım özellikle tek ama ağır contradiction içeren cevaplarla, çok sayıda hafif unsupported claim içeren cevapları birbirinden ayırmak için yararlıdır.

Bu, sistemdeki en kritik doğruluk metriklerinden biridir.

##### Skorlama formülü (capped penalty model)

Claim listesi üretildikten sonra skor türetimi deterministiktir:

```python
_HALLUCINATION_UNSUPPORTED_PENALTY = 0.15   # unsupported claim başına
_HALLUCINATION_CONTRADICTION_PENALTY = 0.30  # confirmed contradiction başına
_FAITHFULNESS_PER_CLAIM_PENALTY = 0.20       # unfaithful claim başına

hallucination_score = max(0.0, 1.0 - toplam_penalty)
faithfulness = max(0.0, 1.0 - unfaithful_count × 0.20)
```

Örnek: 2 unsupported + 1 contradiction → penalty = 0.15 + 0.15 + 0.30 = 0.60 → `hallucination_score = 0.40`
Aynı durumda unfaithful_count = 3 → `faithfulness = max(0.0, 1.0 - 0.60) = 0.40`

Önemli: `agreement` türündeki claim'ler formüle hiç girmez; yalnızca `unsupported claim` ve `confirmed contradiction` penaltı üretir.

##### Paraphrase / inference politikası

Hallucination prompt'u borderline durumlar için açık kural içerir:

> "If the answer paraphrases, summarises, or reasonably infers a fact FROM the context, label it 'agreement'. Exact wording is NOT required."

Örnek: Context "typical use cases include session caching, pub/sub, leaderboards" diyorsa ve answer "Redis is mostly used as a cache" diyorsa → **agreement** (context'ın özeti).

Bu politika hallucination false positive oranını düşürür (paraphrase → agreement); ancak agresif summarization durumlarında gerçek unsupported claim'leri kaçırma riski taşır. Bu trade-off, [8.1.6](#false-positive-false-negative-beklentileri)'daki FP/FN beklentileriyle doğrudan ilgilidir.

#### E. `citation_check`

Bu metrik yalnızca cevap içinde citation benzeri pattern varsa devreye girer. [app/evaluation/rag_metrics.py](app/evaluation/rag_metrics.py) içinde bu davranış açıkça tanımlıdır:

```python
def has_citations(answer: str) -> bool:
  return bool(_CITATION_PATTERN.search(answer))

async def compute_citation_check(
  client: LLMChatClient,
  answer: str,
  contexts: list[str],
) -> float | None:
  if not has_citations(answer):
    return None

  if not contexts:
    return 0.0
```

Prompt mantığı:

```python
CITATION_CHECK_SYSTEM_PROMPT = """
You are a citation verification expert.
For each citation found in the answer:
1. Determine which context passage index the citation claims to reference.
2. Check if that context index actually exists.
3. Verify whether that passage contains the information being cited.
""".strip()
```

Bu metrik şunu söyler:

- model citation verdiğinde gerçekten doğru passage'a mı referans veriyor?

Bu nedenle citation kullanan ürünlerde çok değerlidir; citation üretmeyen ürünlerde ise çoğu zaman `None` olur ve bu beklenen davranıştır.

##### Citation pattern tanıma

`citation_check`'in devreye girip girmediğini belirleyen regex pattern'ler:

```python
_CITATION_PATTERN = re.compile(
    r"\[(\d+)\]"                     # [1], [2], ...
    r"|\[Source\s*(\d+)\]"           # [Source 1], [Source 2], ...
    r"|\(bkz\.?\s*context\s*(\d+)\)" # (bkz. context 1) — Türkçe format
    , re.IGNORECASE,
)
```

Bu pattern'lerden hiçbiri eşleşmezse `citation_check = None` döner. Footnote, URL veya farklı citation formatları tanınmaz.

#### F. `completeness`

`completeness` metrik mantığı iki adımdır:

1. question + context'ten key point çıkar
2. answer bu key point'leri ne kadar kapsıyor kontrol et

Prompt tanımı:

```python
COMPLETENESS_SYSTEM_PROMPT = """
You are a completeness evaluation expert. Your task:
1. Extract the key information requirements (key points) from the question and contexts.
2. For each key point, determine whether the answer adequately covers it.
""".strip()
```

Skorlama mantığı [app/evaluation/rag_metrics.py](app/evaluation/rag_metrics.py) içinde deterministik yapılır:

```python
status_weights = {"covered": 1.0, "partially_covered": 0.5, "not_covered": 0.0}
total_score = sum(
  status_weights.get(kp.get("status", "not_covered"), 0.0)
  for kp in key_points
)
score = round(total_score / total_points, 4) if total_points > 0 else None
```

Ek olarak key point sayısı tamamen LLM'e bırakılmamıştır:

```python
def _key_point_count(question: str) -> int:
  word_count = len(question.split())
  if word_count <= 15:
    return 3
  elif word_count <= 40:
    return 4
  else:
    return 5
```

Bu önemli bir kalite kararıdır. Çünkü denominator sabitlenerek run-to-run oynaklık azaltılmıştır.

#### G. `context_precision`

Bu metrik retrieval tarafının getirdiği context'lerin ne kadarının gerçekten işe yarar olduğunu ölçer.

Prompt tanımı:

```python
CONTEXT_PRECISION_SYSTEM_PROMPT = """
You are a context relevance evaluation expert.
For each context passage, determine if it is relevant to answering the question.
""".strip()
```

Skorlama mantığı:

```python
relevant_count = sum(
  1 for c in ctx_items if isinstance(c, dict) and c.get("relevant") is True
)
total = len(ctx_items)
return round(relevant_count / total, 4) if total > 0 else None
```

Yani bu metrik şu soruya cevap verir:

> Retriever çok fazla gereksiz pasaj mı getiriyor?

#### H. `context_recall`

Bu metrik precision'ın ters bakış açısından çalışır: gerekli bilgi context içinde var mı?

Prompt mantığı:

```python
CONTEXT_RECALL_SYSTEM_PROMPT = """
You are a context recall evaluation expert.

If ground truth is provided:
1. Decompose the ground truth answer into individual factual statements.
2. For each statement, check if any context passage contains this information.

If only a question is provided:
1. Identify the key information needs required to fully answer the question.
2. For each need, check if any context passage provides this information.
""".strip()
```

Skorlama mantığı:

```python
found_count = sum(
  1 for item in items if isinstance(item, dict) and item.get("verdict") == "found"
)
total = len(items)
return round(found_count / total, 4) if total > 0 else None
```

Bu yüzden:

- `context_precision` düşük, `context_recall` yüksek olabilir → çok fazla gereksiz context var ama gerekli bilgi mevcut
- `context_precision` yüksek, `context_recall` düşük olabilir → getirilen az sayıdaki context temiz ama yetersiz

Bu iki metriğin birlikte okunması gerekir.

#### I. `overall_score` neden ayrı bir metrik gibi düşünülmemeli?

`overall_score` kullanıcıya tek skor gibi görünür; ancak teknik olarak birincil kaynak metrik değildir. O, diğer metriklerin ağırlıklı birleşimidir.

Bu nedenle teknik incelemede doğru okuma sırası şudur:

1. önce atomic / component metric'lere bak
2. sonra flag'lere bak
3. en son `overall_score`'u yorumla

Yani `overall_score`, root-cause analizi için başlangıç değil sonuç alanıdır.

### Önemli not: legacy `specificity`

Veritabanında `specificity` kolonu legacy uyumluluk için hâlâ vardır, ancak runtime pipeline tarafından aktif olarak üretilmez ve API response yüzeyinin parçası değildir.

Kaynaklar:
- [app/models/evaluation.py](app/models/evaluation.py)
- [app/schemas/trace.py](app/schemas/trace.py)

---

## 10. Overall Score Hesabı

`overall_score`, LLM'in önerdiği değerin doğrudan kabul edilmesi yerine ağırlıklı bir formülle hesaplanır.

Bu bölüm özellikle önemlidir; çünkü sistemin dışarı verdiği tek üst skor budur ama bu skor doğrudan modelin serbest yargısı değildir. Ürün davranışı [app/evaluation/evaluator.py](app/evaluation/evaluator.py) içindeki deterministic kurallarla kontrol edilir.

> **Çapraz referans:** Ağırlık ve cap seçiminin *tasarım gerekçesi* için [8.1.5 Weight & Cap Rationale](#weight-cap-rationale)'e; uçtan uca sayısal hesap örneği için [8.1.7](#numeric-end-to-end-example)'ye bakınız.

### 10.1 Kodda kullanılan ağırlıklar

İlgili sabitler doğrudan şöyledir:

```python
_OVERALL_WEIGHTS = {
  "hallucination_score": 0.15,
  "faithfulness": 0.10,
  "answer_relevancy": 0.15,
  "completeness": 0.10,
  "context_precision": 0.10,
  "context_recall": 0.10,
  "helpfulness": 0.15,
  "coherence": 0.05,
  "clarity": 0.05,
  "citation_check": 0.05,
}
```

Kullanılan ağırlıklar:

- `hallucination_score`: 0.15
- `faithfulness`: 0.10
- `answer_relevancy`: 0.15
- `completeness`: 0.10
- `context_precision`: 0.10
- `context_recall`: 0.10
- `helpfulness`: 0.15
- `coherence`: 0.05
- `clarity`: 0.05
- `citation_check`: 0.05

Bu dağılım teknik olarak şunu söyler:

- sistem sadece yazı kalitesini ödüllendirmiyor
- retrieval ve grounding tarafı toplam skorun büyük bölümünü etkiliyor
- ama `helpfulness` de yüksek ağırlık aldığı için ürün salt fact-check backend gibi davranmıyor

Yani bu skor, **quality-of-answer** ile **groundedness-of-answer** arasında hibrit bir denge kurar.

### 10.2 Gerçek hesaplama akışı

Hesaplama fonksiyonunun çekirdek mantığı şöyledir:

```python
def _compute_overall_score(
  parsed: dict[str, Any],
  rag_results: dict[str, Any],
  is_deflection: bool = False,
  is_off_topic: bool = False,
  has_contradiction: bool = False,
) -> float | None:
  sources = {
    "hallucination_score": rag_results.get("hallucination_score"),
    "faithfulness": rag_results.get("faithfulness"),
    "completeness": rag_results.get("completeness"),
    "answer_relevancy": rag_results.get("answer_relevancy"),
    "context_precision": rag_results.get("context_precision"),
    "context_recall": rag_results.get("context_recall"),
    "coherence": parsed.get("coherence"),
    "helpfulness": parsed.get("helpfulness"),
    "clarity": parsed.get("clarity"),
    "citation_check": rag_results.get("citation_check"),
  }

  total_weight = 0.0
  weighted_sum = 0.0
  for key, weight in _OVERALL_WEIGHTS.items():
    val = sources.get(key)
    if val is not None:
      val = float(val)
      weighted_sum += val * weight
      total_weight += weight

  if total_weight == 0.0:
    score = parsed.get("overall_score")
  else:
    score = round(weighted_sum / total_weight, 4)
```

Buradan çıkan kritik davranışlar:

- `overall_score`, component metric'lerden yeniden türetilir
- `None` olan alanlar hesap dışı bırakılır
- yalnızca mevcut metric'ler üzerinden normalize edilmiş weighted average alınır
- hiç metric yoksa son çare olarak Stage 2'nin verdiği `overall_score` kullanılır

Bu son madde önemlidir. Çünkü sistem normal koşulda LLM'in overall yargısını değil, **metric bileşimini** esas alır.

### 10.3 Neden yeniden normalize edilmiş weighted average kullanılıyor?

Formül basitçe şu yapıdadır:

$$
overall\_score = \frac{\sum (metric_i \times weight_i)}{\sum weight_i \text{ for non-null metrics}}
$$

Bu yaklaşımın sebebi şudur:

- bazı metric'ler her trace'te gelmeyebilir
- özellikle `citation_check` çoğu zaman `None` olabilir
- eksik bir metriğin tüm skoru yapay olarak aşağı çekmesi istenmez

Dolayısıyla sistem, eksik metric'lerde paydayı da küçültür. Bu, daha adil ama aynı zamanda dikkatle yorumlanması gereken bir tasarımdır.

Teknik uyarı:

- iki trace aynı `overall_score`'a sahip olsa bile, alttaki mevcut metric seti farklı olabilir
- bu yüzden operasyonel debugging sırasında sadece üst skora bakmak yeterli değildir

### 10.4 Guardrail cap'leri

Hesaplama bittikten sonra skor serbest bırakılmaz; ek guardrail cap'leri uygulanır. Koddaki sabitler:

```python
_DEFLECTION_SCORE_CAP = 0.20
_OFF_TOPIC_SCORE_CAP = 0.20
_CONTRADICTION_SCORE_CAP = 0.35
```

Ek cap kuralları:

- `is_deflection=True` ise skor en fazla `0.20`
- `is_off_topic=True` ise skor en fazla `0.20`
- `confirmed contradiction` varsa skor en fazla `0.35`

Uygulama mantığı doğrudan şöyledir:

```python
if is_deflection and score is not None:
  score = min(score, _DEFLECTION_SCORE_CAP)

if is_off_topic and score is not None:
  score = min(score, _OFF_TOPIC_SCORE_CAP)

if has_contradiction and score is not None:
  score = min(score, _CONTRADICTION_SCORE_CAP)
```

Bu tasarımın ürüne etkisi büyüktür:

- cevap akıcı olsa bile deflection ise yüksek skor alamaz
- cevap bazı yan metriklerde iyi görünse bile konu dışıysa yukarı taşınamaz
- açık contradiction varsa yüksek usefulness skoru ürünü kandıramaz

Yani cap mekanizması, ağırlıklı ortalama formülünün üretebileceği hatalı iyimserliği keser.

### 10.5 `confirmed contradiction` nasıl tespit ediliyor?

Contradiction cap'i, hallucination hattından gelen claim listesine dayanır. İlgili yardımcı fonksiyon:

```python
def _has_contradicted_claims(claims: list[dict[str, Any]] | None) -> bool:
  if not claims:
    return False

  for claim in claims:
    if (
      isinstance(claim, dict)
      and str(claim.get("disagreement_type", "")).lower()
      == "confirmed contradiction"
    ):
      return True
  return False
```

Bu, önemli bir ürün kararıdır. Çünkü tüm hallucination türleri aynı ağırlıkta ele alınmaz:

- `unsupported claim` kötü bir sinyal olabilir
- ama `confirmed contradiction` çok daha sert bir cezaya yol açar

Dolayısıyla sistem epistemik risk seviyelerini aynı kefeye koymaz.

### 10.6 `is_off_topic` flag'i tamamen LLM'e mi bırakılıyor?

Hayır. Bu alanda ek deterministik override vardır:

```python
def _coerce_off_topic_flag(
  llm_is_off_topic: Any,
  answer_relevancy: Any,
  helpfulness: Any,
) -> bool:
  try:
    relevancy = float(answer_relevancy)
  except (TypeError, ValueError):
    relevancy = None

  try:
    help_score = float(helpfulness)
  except (TypeError, ValueError):
    help_score = None

  if relevancy == 0.0 and help_score == 0.0:
    return True

  if isinstance(llm_is_off_topic, bool):
    return llm_is_off_topic

  return False
```

Bu şu anlama gelir:

- LLM `is_off_topic=false` dese bile
- eğer `answer_relevancy == 0.0` ve `helpfulness == 0.0` ise
- sistem deterministic olarak cevabı off-topic kabul eder

Bu, üretimde çok değerli bir güvenlik katmanıdır.

### 10.7 Teknik olarak bu skor nasıl okunmalı?

Teknik ekip için doğru okuma şu şekildedir:

1. `hallucination_score`, `faithfulness`, `answer_relevancy`, `completeness` gibi kök metriklere bak
2. `is_off_topic`, `is_deflection`, contradiction var mı kontrol et
3. en son `overall_score`'u yorumla

Çünkü `overall_score` root-cause taşıyan ham veri değil, kurallarla işlenmiş final ürün skorudur.

### 10.8 Güçlü ve zayıf yönler

#### Güçlü yönler

- deterministik davranış sağlar
- tek bir judge skoruna kör bağımlılığı azaltır
- guardrail cap'leri ile bariz kötü cevapların yüksek skor almasını engeller
- eksik metric'ler varken bile hesap yapılabilir

#### Zayıf yönler

- ağırlıklar ürün tercihidir; evrensel gerçek değildir
- farklı kullanım senaryolarında aynı ağırlık seti optimal olmayabilir
- eksik metric'lerde normalize hesap yapmak bazı trace'leri olduğundan iyi gösterebilir
- tek üst skora fazla odaklanan kullanıcılar alt metrikleri gözden kaçırabilir

Kaynak:
- [app/evaluation/evaluator.py](app/evaluation/evaluator.py)

### 10.9 Maliyet hesaplama mantığı

Token maliyeti şu formülle hesaplanır:

```
cost = (stage1_prompt_tokens × stage1_input_price / 1M)
     + (stage1_completion_tokens × stage1_output_price / 1M)
     + (stage2_prompt_tokens × stage2_input_price / 1M)
     + (stage2_completion_tokens × stage2_output_price / 1M)
```

Varsayılan fiyatlar ([app/config.py](app/config.py)):

- Stage 1 (gpt-5.2): input $2.50/M token, output $10.00/M token
- Stage 2 (gpt-4o-mini): input $0.15/M token, output $0.60/M token

**Önemli:** RAG metric token'ları Stage 2 token bucket'ına eklenir ve Stage 2 fiyatıyla hesaplanır (kendi modeli `gpt-5-mini` olmasına rağmen). Bu, maliyet raporlarında RAG maliyetinin olduğundan düşük görünmesine neden olabilir.

Kaynak: [app/evaluation/evaluator.py](app/evaluation/evaluator.py), [app/config.py](app/config.py)

---

## 11. Multi-Agent / Step Evaluation

Sistem, trace metadata içinde `steps` varsa multi-agent bir trace olarak davranabilir.

Bu durumda:

1. final trace normal şekilde evaluate edilir
2. her step için ayrı evaluation çalışır
3. step sonuçları paralel toplanır
4. `pipeline_score = 0.5 * trace_score + 0.5 * avg(step_scores)` olarak hesaplanır

Kaynaklar:
- [app/services/evaluation_service.py](app/services/evaluation_service.py)
- [app/models/evaluation.py](app/models/evaluation.py)
- [app/schemas/trace.py](app/schemas/trace.py)

### Multi-agent tetikleyici

Temel olarak `metadata.steps` alanı kullanılır.

SDK tarafında benzer metadata üretimi için:
- [sdk/rageval_callback.py](sdk/rageval_callback.py)

---

## 12. Webhook Davranışı

Trace ingest sırasında `webhook_url` verilirse evaluation tamamlandıktan sonra callback gönderilir.

### Davranış

- event tipi: `evaluation.completed`
- trace id, durum, skorlar, verdicts, flags, details döner
- `reasoning_summary`, `evaluation_commentary`, `cost_usd`, `total_tokens` döner
- başarısız çağrılarda exponential backoff ile retry uygulanır

### Batch davranışı

`POST /api/v1/ingest/batch` isteğinde batch-level `webhook_url` verilebilir. Trace'in kendi `webhook_url` değeri yoksa bu değer trace'lere aktarılır.

---

## 13. Veri Modeli

### 13.1 `users`

Temel alanlar:

- `id`
- `email`
- `hashed_password`
- `api_key_hash`
- `api_key_prefix`
- `is_active`
- `created_at`
- `updated_at`

Kaynak:
- [app/models/user.py](app/models/user.py)

### 13.2 `traces`

Temel alanlar:

- `id`
- `user_id`
- `question`
- `answer`
- `contexts`
- `ground_truth`
- `metadata`
- `status`
- `webhook_url`
- `created_at`
- `updated_at`

Kaynak:
- [app/models/trace.py](app/models/trace.py)

### 13.3 `evaluation_results`

Temel alanlar:

- rubric skorları ve flag'ler
- RAG metric skorları
- `reasoning_summary`
- `stage_1_reasoning`
- `raw_response`
- `hallucination_claims`
- `completeness_key_points`
- `pipeline_score`
- `content_hash`
- `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_usd`
- `evaluation_duration_ms`
- `model_used`, `prompt_version`, `rubric_version`

Kaynak:
- [app/models/evaluation.py](app/models/evaluation.py)

### 13.4 `step_evaluation_results`

Multi-agent trace'lerde step bazlı evaluation sonuçları burada tutulur.

---

## 14. Konfigürasyon

Temel ayarlar [app/config.py](app/config.py) içindedir.

### Zorunlu
- `DATABASE_URL`

### OpenAI
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_TIMEOUT_SECONDS`

### Model seçimi
- `STAGE_1_MODEL` → varsayılan `gpt-5.2`
- `STAGE_2_MODEL` → varsayılan `gpt-4o-mini`
- `RAG_METRICS_MODEL` → varsayılan `gpt-5-mini`

### Evaluation çalışma modu
- `EVALUATION_MODE=sync|async`

### Celery / Redis
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`

### Webhook
- `WEBHOOK_SECRET`
- `WEBHOOK_TIMEOUT_SECONDS`
- `WEBHOOK_MAX_RETRIES`

### CORS
- `CORS_ORIGINS`

### Prompt truncation
- `MAX_QUESTION_CHARS`
- `MAX_ANSWER_CHARS`
- `MAX_CONTEXT_TOTAL_CHARS`
- `MAX_SINGLE_CONTEXT_CHARS`
- `MAX_GROUND_TRUTH_CHARS`

---

## 15. Çalıştırma ve Ortamlar

### Docker Compose servisleri

[docker-compose.yml](docker-compose.yml) ile şu servisler ayağa kalkar:

- `migrate`
- `api`
- `worker`
- `redis`
- `db`
- `pgadmin`

### Sync ve async farkı

#### `sync`
- tekli ingest'te evaluation doğrudan çağrı akışında çalışır
- batch ingest ise arka plan thread'i ile başlatılır

#### `async`
- evaluation Celery task olarak kuyruklanır
- batch için Celery group kullanılır

### Shutdown davranışı

Uygulama kapanırken:

- aktif batch thread'leri beklenir
- paylaşılan OpenAI HTTP client kapatılır

---

## 16. Testler ve Doğrulama

Repo içinde başlıca test alanları:

- [tests/test_auth_service.py](tests/test_auth_service.py)
- [tests/test_evaluation_service.py](tests/test_evaluation_service.py)
- [tests/test_evaluator.py](tests/test_evaluator.py)
- [tests/test_rag_metrics.py](tests/test_rag_metrics.py)
- [tests/test_schemas.py](tests/test_schemas.py)
- [tests/e2e_docker_scenarios.sh](tests/e2e_docker_scenarios.sh)

Bu testler özellikle şu alanları kapsar:

- auth servisleri
- evaluator yardımcıları
- scoring ve schema davranışı
- RAG metric fonksiyonları
- validation ve request/response şemaları

---

## 17. Bilinen Sınırlar

1. LLM tabanlı evaluation deterministik değildir; aynı trace'te küçük varyasyonlar olabilir.
2. `sync` modda tekli ingest çağrısı, evaluation süresine bağlı olarak uzun sürebilir.
3. `citation_check`, cevapta citation paterni yoksa doğal olarak `None` dönebilir.
4. `metrics/definitions` endpoint'i public'tir; auth isteyen endpoint'lerden ayrıdır.
5. `specificity` legacy kolondur; aktif ürün metriği olarak ele alınmamalıdır.
6. `ground_truth` aktif olarak kullanılmaktadır; yalnızca gelecek planı değildir.
7. SDK klasöründe yardımcı kod vardır, fakat paketlenmiş resmi bir `pip install` SDK yüzeyi bu repoda tanımlı değildir.

---


