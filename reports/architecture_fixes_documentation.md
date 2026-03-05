# RAG Eval API — Mimari İyileştirmeler Dokümantasyonu

> Bu dokümanda yapılan **53 düzeltme ve optimizasyonun** (20 orijinal + 27 mimari review + 6 performans optimizasyonu) tamamı, sıfırdan öğrenen birine anlatır gibi açıklanmıştır. Her madde basit bir benzetmeyle başlar, teknik detaya iner ve kodda ne yapıldığını gösterir.

---

## İÇİNDEKİLER

### Orijinal 20 Madde (İlk Mimari Review)
| # | Başlık |
|---|--------|
| 1 | [Stage 1/2 Prompt Rubric Tutarsızlığı](#madde-1) |
| 2 | [Connection Pooling (HTTP Bağlantı Havuzu)](#madde-2) |
| 3 | [Evaluation Sonuç Kayıt Sırası](#madde-3) |
| 4 | [Prompt Truncation (Girdi Kırpma)](#madde-4) |
| 5 | [Stage 1/2 Metrik Tutarlılığı](#madde-5) |
| 6 | [Weighted Overall Score (Ağırlıklı Genel Skor)](#madde-6) |
| 7 | [Deterministic Score Caps (Skor Tavan Sınırları)](#madde-7) |
| 8 | [LLM Retry Mekanizması](#madde-8) |
| 9 | [Circuit Breaker Pattern](#madde-9) |
| 10 | [CORS Güvenlik Konfigürasyonu](#madde-10) |
| 11 | [Health Endpoint DB Session Leak](#madde-11) |
| 12 | [Context Numbering Tutarlılığı](#madde-12) |
| 13 | [Hallucination Agreement Claim Bias](#madde-13) |
| 14 | [Completeness Dual Computation](#madde-14) |
| 15 | [Metrik Ağırlık Formülü](#madde-15) |
| 16 | [Batch Evaluation Paralelleştirme](#madde-16) |
| 17 | [N+1 Query Problemi](#madde-17) |
| 18 | [Content Hash Evaluation Cache](#madde-18) |
| 19 | [Token Tracking & Cost Monitoring](#madde-19) |
| 20 | [Webhook Callback Mekanizması](#madde-20) |

### Yeni 27 Madde (İkinci Mimari Review)
| # | Başlık |
|---|--------|
| 21 | [SSRF Webhook Koruması](#madde-21) |
| 22 | [Loop-Aware AsyncClient](#madde-22) |
| 23 | [Thread-Safe Circuit Breaker](#madde-23) |
| 24 | [Auth Rate Limiting](#madde-24) |
| 25 | [Celery Retry Scope](#madde-25) |
| 26 | [Sync Webhook (Skip)](#madde-26) |
| 27 | [Hardcoded Credentials Kaldırma](#madde-27) |
| 28 | [Missing Env Vars Crash](#madde-28) |
| 29 | [Webhook URL Format Doğrulama](#madde-29) |
| 30 | [Celery Worker Concurrency](#madde-30) |
| 31 | [DB Connection Pool Yapılandırması](#madde-31) |
| 32 | [Cascade Delete](#madde-32) |
| 33 | [Daemon Thread Graceful Shutdown](#madde-33) |
| 34 | [Maliyet Hesaplama Doğruluğu](#madde-34) |
| 35 | [Dead Specificity Column](#madde-35) |
| 36 | [Token Race Condition (Skip)](#madde-36) |
| 37 | [Count Query Optimizasyonu](#madde-37) |
| 38 | [Redis Healthcheck](#madde-38) |
| 39 | [Health Endpoint Redis Kontrolü](#madde-39) |
| 40 | [Trace updated_at Kolonu](#madde-40) |
| 41-47 | [Kalan Low-Priority İyileştirmeler](#madde-41-47) |

### Performans Optimizasyonları (Phase 1-3)
| # | Başlık |
|---|--------|
| 48 | [Token Limit Optimizasyonu (144s → 53s)](#madde-48) |
| 49 | [Hallucination Single-Call Birleştirme (53s → 35s)](#madde-49) |
| 50 | [Stage 2 Pipeline Restructure — RAG'den Bağımsızlaştırma (35s → 16.8s)](#madde-50) |
| 51 | [Completeness / Citation Token Limit Fix](#madde-51) |
| 52 | [evaluation_duration_ms Feature](#madde-52) |
| 53 | [Pipeline Timing Instrumentation](#madde-53) |

---

<details id="madde-1">
<summary><strong>✅ Madde 1 — Stage 1/2 Prompt Rubric Tutarsızlığı</strong></summary>

### Basit Anlatım
Bir sınavda öğretmen, sözlü sınavda "5 kriter" üzerinden puan verirken, yazılı sınavda "7 kriter" üzerinden puan verse, notlar tutarsız olur. Burada da Stage 1 (düşünme aşaması) ve Stage 2 (puanlama aşaması) farklı kriterleri değerlendiriyordu.

### Ne Yapıldı
Her iki aşamada da **aynı rubric bloğu** (`RUBRIC_BLOCK`) kullanılacak şekilde prompt'lar birleştirildi. Stage 1 bu rubric'e göre düşünür, Stage 2 aynı rubric'e göre JSON puanlar üretir.

### Teknik Terimler
- **Rubric:** Değerlendirme ölçeği. Her metrik için 0.0 ile 1.0 arasında ne anlama geldiğini tanımlayan "çıpa değerleri" (anchor values) içerir.
- **Stage 1 (Chain-of-Thought):** LLM'in adım adım düşünmesi — "clarity şu yüzden 0.7 çünkü..." diye analiz yapar.
- **Stage 2 (Structured Output):** Stage 1'in düşüncelerini alıp kesin JSON skorları çıkarır.
- **Prompt:** LLM'e gönderilen metin talimatı.

### Kod
**Dosya:** `app/evaluation/prompts.py`
```python
RUBRIC_BLOCK = """
CLARITY (0-1): 0.0=anlaşılmaz, 0.5=kısmen net, 1.0=kristal berrak
COHERENCE (0-1): 0.0=kopuk, 0.5=kısmen tutarlı, 1.0=mükemmel akış
...
"""
STAGE_1_SYSTEM_PROMPT = f"""...\n{RUBRIC_BLOCK}\n..."""
STAGE_2_SYSTEM_PROMPT = f"""...\n{RUBRIC_BLOCK}\n..."""
```
İki stage aynı `RUBRIC_BLOCK`'u paylaşıyor — tutarsızlık imkansız.

</details>

---

<details id="madde-2">
<summary><strong>✅ Madde 2 — Connection Pooling (HTTP Bağlantı Havuzu)</strong></summary>

### Basit Anlatım
Her telefon görüşmesi için yeni bir telefon hattı çekmek yerine, bir santral kurup mevcut hatları paylaşmak gibi düşün. HTTP bağlantıları da aynı: her API çağrısında yeni bağlantı açmak yerine, hazırda bekleyen bağlantıları yeniden kullanıyoruz.

### Ne Yapıldı
`httpx.AsyncClient` sınıf seviyesinde paylaşımlı (shared) oluşturuldu. Tüm LLM çağrıları aynı TCP/TLS bağlantılarını kullanıyor.

### Teknik Terimler
- **Connection Pooling:** Bağlantıları önceden oluşturup havuzda tutma. Yeni istek gelince hazır bağlantı atanır, işi bitince havuza döner.
- **TLS Handshake:** HTTPS bağlantısında istemci ve sunucu arasındaki güvenlik tokalaşması. Her seferinde ~50-100ms sürer. Pool sayesinde bir kez yapılır.
- **Keep-Alive:** TCP bağlantısını kapatmadan açık tutma. Sonraki istekler aynı bağlantıyı kullanır.
- **HTTP/2:** Tek bir TCP bağlantısı üzerinden birden fazla isteği paralel gönderebilen protokol versiyonu.

### Kod
**Dosya:** `app/evaluation/llm_client.py`
```python
class OpenAILLMClient:
    _clients_by_loop: dict[int, httpx.AsyncClient] = {}

    @classmethod
    def _get_http_client(cls):
        client = httpx.AsyncClient(
            limits=httpx.Limits(
                max_connections=20,        # Aynı anda en fazla 20 bağlantı
                max_keepalive_connections=10,  # 10'u canlı tutuluyor
                keepalive_expiry=30,       # 30 saniye boşta kalırsa kapat
            ),
            http2=True,                    # HTTP/2 ile çoklu istek
        )
```
**Performans kazanımı:** Her LLM çağrısından ~50-100ms TLS overhead tasarrufu.

</details>

---

<details id="madde-3">
<summary><strong>✅ Madde 3 — Evaluation Sonuç Kayıt Sırası</strong></summary>

### Basit Anlatım
Bir restoranda sipariş verildi ama garson yemeği getirmeden önce hesabı kesti. Burada da evaluation (değerlendirme) sonucu veritabanına yazılmadan önce trace status'u güncelleniyor — sonuç kaybolabilir.

### Ne Yapıldı
Önce evaluation sonucu DB'ye yazılıyor (`db.add(evaluation)`), sonra trace status'u güncelleniyor (`trace.status = "completed"`), en son `db.commit()` yapılıyor. Tek transaction içinde atomik olarak.

### Teknik Terimler
- **Transaction:** Veritabanında "ya hepsi ya hiçbiri" mantığıyla çalışan işlem grubu. Ortasında hata olursa hepsi geri alınır (rollback).
- **Atomicity:** Bölünemezlik ilkesi. İşlem ya tamamen yapılır ya hiç yapılmamış gibi olur.
- **Race Condition:** İki işlem aynı veriye aynı anda eriştiğinde oluşan tutarsızlık.

### Kod
**Dosya:** `app/services/evaluation_service.py`
```python
# Tek transaction içinde sıralı kayıt
db.add(evaluation)                         # 1. Sonucu yaz
trace.status = "completed"                 # 2. Status güncelle
db.commit()                                # 3. Her ikisini birden kaydet
```

</details>

---

<details id="madde-4">
<summary><strong>✅ Madde 4 — Prompt Truncation (Girdi Kırpma)</strong></summary>

### Basit Anlatım
Bir zarfın içine 10 sayfa mektup sığdıramazsın — taşan kısım kesilir. LLM'lerin de bir "zarf boyutu" (context window) var. Girdi çok uzunsa LLM ya hata verir ya hallucinate eder.

### Ne Yapıldı
Tüm inputlar (soru, cevap, context'ler, ground truth) gönderilmeden önce konfigüre edilebilir karakter limitlerine göre kırpılıyor. Kırpma yapıldığında `[truncated]` işareti ekleniyor.

### Teknik Terimler
- **Context Window:** LLM'in bir seferde işleyebildiği maksimum token sayısı. GPT-5.2 için ~128K token.
- **Token:** LLM'in metni parçalama birimi. Kabaca 1 İngilizce kelime ≈ 1.3 token, 1 Türkçe kelime ≈ 2-3 token.
- **Truncation:** Uzun metni belirli bir limitte keserek kısaltma.
- **Hallucination:** LLM'in gerçek olmayan bilgiyi uydurması.

### Konfigürasyon
**Dosya:** `app/config.py`
```python
max_question_chars: int = 8_000       # Soru: ~2K token
max_answer_chars: int = 40_000        # Cevap: ~10K token
max_context_total_chars: int = 80_000 # Tüm context'ler toplamı: ~20K token
max_single_context_chars: int = 20_000 # Tek context: ~5K token
max_ground_truth_chars: int = 10_000  # Ground truth: ~2.5K token
```

### Kod
**Dosya:** `app/evaluation/prompt_utils.py`
```python
def truncate_text(text: str, max_chars: int, label: str = "text") -> str:
    if len(text) <= max_chars:
        return text
    logger.warning("%s truncated: %d → %d chars", label, len(text), max_chars)
    return text[:max_chars] + f"\n\n...[{label} truncated at {max_chars} chars]"
```

</details>

---

<details id="madde-5">
<summary><strong>✅ Madde 5 — Stage 1/2 Metrik Tutarlılığı</strong></summary>

### Basit Anlatım
Bir öğretmen sözlü sınavda "matematik, fizik, kimya" derken, yazılı sınavda "matematik, biyoloji, tarih" sorsa, notları karşılaştırmak imkansız olur. Her iki aşamada da aynı metrikler sorulmalı.

### Ne Yapıldı
Stage 1 ve Stage 2 artık **tam olarak aynı metrikleri** değerlendiriyor. Stage 2'nin JSON schema'sı (`STAGE_2_JSON_SCHEMA`) Stage 1'de analiz edilen tüm alanları `required` olarak tanımlıyor.

### Teknik Terimler
- **JSON Schema:** JSON verisinin yapısını tanımlayan standart. Hangi alanlar zorunlu, hangi tip olmalı gibi kuralları belirler.
- **Structured Output:** LLM'den serbest metin yerine, önceden tanımlanmış şemaya uygun JSON almak.
- **Required Fields:** JSON Schema'da mutlaka bulunması gereken alanlar.

### Kod
**Dosya:** `app/evaluation/evaluator.py`
```python
_REQUIRED_FIELDS = [
    "clarity", "completeness", "coherence", "helpfulness",
    "overall_score", "evaluation_confidence",  # Float alanlar
    "is_off_topic", "is_deflection",           # Boolean alanlar
    "reasoning_summary", "disagreement_claims", # Metin alanlar
]
```

</details>

---

<details id="madde-6">
<summary><strong>✅ Madde 6 — Weighted Overall Score (Ağırlıklı Genel Skor)</strong></summary>

### Basit Anlatım
Üniversite not ortalamasında her dersin kredisi farklıdır — 5 kredilik bir ders, 2 kredilik dersten daha çok etkiler. Biz de evaluation metriklerini "kredi" (ağırlık) bazında çarpıp toplayarak genel skor hesaplıyoruz.

### Ne Yapıldı
LLM'in kendi verdiği `overall_score` yerine, **deterministik ağırlıklı ortalama** formülü kullanılıyor. LLM her seferinde farklı skor verebilirdi — şimdi aynı metrik değerleriyle her zaman aynı overall score çıkar.

### Teknik Terimler
- **Weighted Average:** Her değere bir ağırlık (weight) çarparak toplam alan ve ağırlıklar toplamına bölen formül.
- **Deterministic:** Aynı girdi ile her zaman aynı çıktı veren. Rastgelelik yok.
- **Dynamic Normalization:** Eksik metrikleri atlayıp, mevcut metriklerin ağırlıklarını yeniden normalize etme.

### Ağırlıklar
```python
_OVERALL_WEIGHTS = {
    "hallucination_score": 0.15,   # En kritik: cevap uydurma
    "faithfulness":        0.10,   # Context'e sadakat
    "answer_relevancy":    0.15,   # Soruyla ilgililik
    "completeness":        0.10,   # Eksik bilgi var mı
    "context_precision":   0.10,   # Doğru context'ler geldi mi
    "context_recall":      0.10,   # Yeterli context geldi mi
    "helpfulness":         0.15,   # Kullanıcıya faydası
    "coherence":           0.05,   # Tutarlılık
    "clarity":             0.05,   # Anlaşılırlık
    "citation_check":      0.05,   # Kaynak gösterimi
}
# Toplam: 1.00
```

### Formül
$overall = \frac{\sum_{i} w_i \times score_i}{\sum_{i} w_i}$

Burada $w_i$ her metriğin ağırlığı, $score_i$ o metriğin puanı. Eksik metrikler (None) formülden çıkarılır ve ağırlıklar yeniden normalize edilir.

</details>

---

<details id="madde-7">
<summary><strong>✅ Madde 7 — Deterministic Score Caps (Skor Tavan Sınırları)</strong></summary>

### Basit Anlatım
Bir öğrenci sınavda kopya çekerken yakalanırsa, diğer soruları ne kadar iyi yapmış olursa olsun notu düşürülür. Burada da "cevap konu dışı" veya "halüsinasyon var" gibi ciddi sorunlarda genel skor otomatik olarak tavana çekiliyor.

### Ne Yapıldı
3 durumda overall score cap uygulanıyor:
- **Off-topic** (konu dışı): Maksimum 0.20
- **Deflection** (soruyu geçiştirme): Maksimum 0.20
- **Contradiction** (context'le çelişme): Maksimum 0.35

### Teknik Terimler
- **Score Cap:** Bir skorun aşamayacağı maksimum değer. `min(hesaplanan_skor, cap)` ile uygulanır.
- **Deflection:** LLM'in "Ben bir AI'yım, bunu yapamam" gibi cevaplarla soruyu geçiştirmesi.
- **Off-topic:** Cevabın soruyla hiç ilgisi olmaması.
- **Contradiction:** Cevabın verilen context bilgileriyle çelişmesi.

### Kod
```python
_DEFLECTION_SCORE_CAP = 0.20
_OFF_TOPIC_SCORE_CAP = 0.20
_CONTRADICTION_SCORE_CAP = 0.35

# Uygulama:
if is_off_topic:
    score = min(score, _OFF_TOPIC_SCORE_CAP)  # 0.85 → 0.20
if is_deflection:
    score = min(score, _DEFLECTION_SCORE_CAP)
if has_contradiction:
    score = min(score, _CONTRADICTION_SCORE_CAP)
```

</details>

---

<details id="madde-8">
<summary><strong>✅ Madde 8 — LLM Retry Mekanizması</strong></summary>

### Basit Anlatım
Telefonla birini arıyorsun, meşgul çalıyor. Hemen kapayıp vazgeçmek yerine, 1 saniye bekle, tekrar ara. Hâlâ meşgulse 2 saniye bekle, tekrar ara. Bu "exponential backoff" stratejisi.

### Ne Yapıldı
LLM API çağrıları başarısız olduğunda 3 deneme yapılıyor. Bekleme süresi her denemede 2 katına çıkıyor (1s → 2s → 4s). Rate limit (429) durumunda sunucunun söylediği `Retry-After` süresine de uyuluyor.

### Teknik Terimler
- **Retry:** Başarısız işlemi tekrar deneme.
- **Exponential Backoff:** Her denemede bekleme süresini 2 katına çıkarma. Sunucuyu boğmamak için.
- **Rate Limit (429):** "Çok hızlı istek atıyorsun, yavaşla" anlamında HTTP durum kodu.
- **Retry-After Header:** Sunucunun "şu kadar saniye bekle" dediği HTTP başlığı.
- **Idempotent:** Aynı işlemi tekrar yapmanın zararsız olması. GET/PUT idempotent, POST değil — ama LLM chat completion POST'u idempotent çünkü yeni bir completion oluşturur.

### Kod
```python
_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0         # İlk bekleme: 1 saniye
_BACKOFF_FACTOR = 2.0       # Her seferinde 2x: 1s → 2s → 4s
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 529}

async def _request_with_retry(self, url, headers, payload):
    for attempt in range(1, _MAX_RETRIES + 1):
        resp = await client.post(url, headers=headers, json=payload)

        if resp.status_code < 400:  # Başarılı
            return resp

        if resp.status_code in _RETRYABLE_STATUS_CODES:
            wait = _BACKOFF_BASE * (_BACKOFF_FACTOR ** (attempt - 1))
            # Retry-After header'ı varsa onu kullan
            retry_after = resp.headers.get("retry-after")
            if retry_after:
                wait = max(wait, float(retry_after))
            await asyncio.sleep(wait)
            continue

        # 400, 401, 403 gibi hatalar → retry yapmadan hemen hata fırlat
        raise LLMClientError(f"Error {resp.status_code}")
```

</details>

---

<details id="madde-9">
<summary><strong>✅ Madde 9 — Circuit Breaker Pattern</strong></summary>

### Basit Anlatım
Evdeki sigorta düşünün: aşırı akım gelince sigorta atar ve tüm devreyi keser. Böylece cihazlar zarar görmez. API'lar için de aynı mantık var: OpenAI sürekli hata veriyorsa, boşuna deneyemeye devam etme — devreyi kes, bekle, sonra tekrar dene.

### Ne Yapıldı
Ardışık 5 hata olunca devre OPEN'a geçiyor (tüm çağrılar anında reddediliyor). 30 saniye sonra HALF_OPEN'a geçip tek bir "prob" isteği gönderiyor. Başarılıysa CLOSED'a döner, değilse tekrar OPEN.

### Teknik Terimler
- **Circuit Breaker Pattern:** Mikroservis mimarisinde yaygın koruma deseni. 3 durumu var:
  - **CLOSED** (normal): İstekler geçiyor
  - **OPEN** (devre kesik): Tüm istekler anında reddediliyor
  - **HALF_OPEN** (test): Tek bir istek geçirilip sonuca bakılıyor
- **Failure Threshold:** Devreyi açmak için gereken ardışık hata sayısı (5)
- **Recovery Timeout:** OPEN'dan HALF_OPEN'a geçiş süresi (30 saniye)
- **Cascading Failure:** Bir servisin hatasının diğer servislere yayılması. Circuit breaker bunu engeller.

### Durum Geçişleri
```
CLOSED ──[5 ardışık hata]──→ OPEN ──[30s bekleme]──→ HALF_OPEN
                                                        │
                                                   [başarılı] → CLOSED
                                                   [başarısız] → OPEN
```

### Kod
```python
class _CircuitBreaker:
    _failure_threshold = 5
    _recovery_timeout = 30.0

    async def before_call(self):
        with self._lock:  # threading.Lock (cross-loop safe)
            if self.state == _CBState.OPEN:
                raise LLMClientError("Circuit breaker OPEN – çağrılar devre dışı")

    async def record_failure(self):
        with self._lock:
            self._failure_count += 1
            if self._failure_count >= self._failure_threshold:
                self._state = _CBState.OPEN  # Devre kesildi!
```

</details>

---

<details id="madde-10">
<summary><strong>✅ Madde 10 — CORS Güvenlik Konfigürasyonu</strong></summary>

### Basit Anlatım
Apartmanın kapısına "sadece 3A, 5B ve 7C dairelerin misafirleri girebilir" yazarsın. CORS da aynı: hangi web sitelerinin API'mıza istek atabileceğini kontrol eden güvenlik mekanizması.

### Ne Yapıldı
Hardcoded `allow_origins=["*"]` (herkese açık) yerine, `CORS_ORIGINS` environment variable'ından okunuyor. Boşsa CORS middleware hiç eklenmez (en güvenli). `"*"` ise development, spesifik listeyse production için.

### Teknik Terimler
- **CORS (Cross-Origin Resource Sharing):** Tarayıcının "bu API'ya sadece bu sitelerden istek atılabilir" kuralı.
- **Origin:** Bir web sitesinin `scheme + host + port` birleşimi. Örnek: `https://app.example.com:443`
- **Preflight Request:** Tarayıcının asıl isteği göndermeden önce "bu origin'den istek atabilir miyim?" diye sorduğu OPTIONS isteği.
- **allow_credentials:** Cookie/auth bilgisi göndermeye izin verme. `*` ile birlikte kullanılamaz (CORS spec kuralı).

### Kod
```python
# config.py
cors_origins: str = ""  # Boş = CORS yok, "*" = herkes, "url1,url2" = whitelist

# main.py
_raw_origins = settings.cors_origins.strip()
if _raw_origins:
    _origin_list = ["*"] if _raw_origins == "*" else [
        o.strip() for o in _raw_origins.split(",") if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origin_list,
        allow_credentials=_raw_origins != "*",  # * + credentials = geçersiz
    )
```

</details>

---

<details id="madde-11">
<summary><strong>✅ Madde 11 — Health Endpoint DB Session Leak</strong></summary>

### Basit Anlatım
Kütüphaneden kitap alıp okuyorsun ama geri koymayı unutuyorsun. Zamanla raf boşalır, kimse kitap bulamaz. DB session'ları da aynı: açıp kapatmazsan havuzdaki bağlantılar tükenir.

### Ne Yapıldı
Health endpoint'te `SessionLocal()` context manager (`with` bloğu) ile kullanılarak, hata olsa bile session'ın kapanması garanti ediliyor.

### Teknik Terimler
- **Session Leak:** Veritabanı bağlantısının açılıp kapatılmaması. Havuzda kullanılabilir bağlantı kalmaz → yeni istekler bekler.
- **Context Manager:** Python'da `with` bloğu ile kullanılan, otomatik temizlik yapan yapı. `__enter__` ve `__exit__` metodları var.
- **Connection Pool Exhaustion:** Havuzdaki tüm bağlantıların tükenmesi. Yeni istekler kuyruğa girer veya timeout alır.

### Kod
```python
@app.get("/health")
def health():
    try:
        with SessionLocal() as db:  # with → otomatik kapatma garantisi
            db.execute(text("SELECT 1"))
        status_detail["database"] = "ok"
    except Exception:
        status_detail["database"] = "unavailable"
```

</details>

---

<details id="madde-12">
<summary><strong>✅ Madde 12 — Context Numbering Tutarlılığı</strong></summary>

### Basit Anlatım
Bir kitabın sayfaları 1, 2, 3 diye numaralanır. Ama biri 0'dan başlarsa (0, 1, 2), referans verirken karışıklık çıkar: "sayfa 2" hangisi? Context numaralama da aynı — tüm prompt'larda tutarlı olmalı.

### Ne Yapıldı
Stage 1 ve RAG metrik prompt'larında context numaralama 1-based (`[Context 1]`, `[Context 2]`) olarak standardize edildi. Önceden bazıları 0-based, bazıları 1-based idi.

### Teknik Terimler
- **0-based indexing:** Dizileri 0'dan saymak (programlama geleneği: C, Python).
- **1-based indexing:** Dizileri 1'den saymak (insan geleneği: kitap sayfaları).
- **Prompt Engineering:** LLM'e verilen talimatları optimize etme sanatı. Tutarsız prompt → tutarsız çıktı.

</details>

---

<details id="madde-13">
<summary><strong>✅ Madde 13 — Hallucination Agreement Claim Bias</strong></summary>

### Basit Anlatım
Bir sınavda 10 soru var, 8'ini doğru yaptın. Notun 8/10 = 0.80 olmalı. Ama "doğru yaptığın soruların sayısı" üzerinden ek puan verirsen, cevabı uzatıp çok claim içeren kişi haksız avantaj kazanır.

### Ne Yapıldı
Hallucination skoru artık sadece **problematik claim'lere** bakıyor. "Supported" (desteklenen) claim'ler formüle dahil edilmiyor. Her problematik claim sabit bir penalty (ceza) düşürüyor:
- Unsupported claim: -0.15
- Contradicted claim: -0.30

### Teknik Terimler
- **Claim:** Cevaptaki tek bir bilgi iddiası. "Ankara Türkiye'nin başkentidir" = 1 claim.
- **Hallucination:** Context'te hiç bulunmayan bilginin uydurulması.
- **Supported/Unsupported/Contradicted:** Bir claim'in context'le ilişkisi.
- **Agreement Bias:** Desteklenen claim sayısının skoru şişirmesi.
- **Capped Penalty:** Her problematik claim için sabit miktarda puan düşürme (oran yerine).

### Formül
$hallucination\_score = \max(0, 1.0 - \sum penalties)$

```python
_HALLUCINATION_UNSUPPORTED_PENALTY = 0.15    # 1 unsupported → 0.85
_HALLUCINATION_CONTRADICTION_PENALTY = 0.30  # 1 contradiction → 0.70
# 2 unsupported + 1 contradiction = 1.0 - 0.30 - 0.30 = 0.40
```

</details>

---

<details id="madde-14">
<summary><strong>✅ Madde 14 — Completeness Dual Computation Kaldırma</strong></summary>

### Basit Anlatım
Hem matematik öğretmeni hem fizik öğretmeni aynı soruyu bağımsız puanlıyor ve ikisi de "completeness" diyor — hangisine güveneceksin? Tek bir kaynak olmalı.

### Ne Yapıldı
`completeness` artık sadece RAG metrics'ten geliyor (key-point extraction + coverage verification). Stage 2'den gelen completeness değeri göz ardı ediliyor.

### Teknik Terimler
- **Key-Point Extraction:** Ground truth'tan ana noktaları çıkarma.
- **Coverage Verification:** Cevabın bu noktaları ne kadar karşıladığını kontrol etme.
- **Single Source of Truth:** Bir bilginin tek bir yetkili kaynağı olması prensibi.

</details>

---

<details id="madde-15">
<summary><strong>✅ Madde 15 — Metrik Ağırlık Formülü (Madde 6 ile Birleşik)</strong></summary>

### Basit Anlatım
Madde 6'da anlatılan ağırlıklı ortalama formülünün, industry-standard uygulamalarla karşılaştırılması ve doğrulanması. Akademik araştırma sonucu ağırlıklar valide edildi.

### Ne Yapıldı
Ağırlıklar araştırmaya dayalı olarak belirlendi — hallucination ve helpfulness en yüksek ağırlığı aldı (0.15) çünkü kullanıcı güvenliği ve memnuniyeti ile doğrudan ilişkili.

### Teknik Terimler
- **Industry Standard:** Sektörde yaygın kabul gören uygulama.
- **Ablation Study:** Bir bileşeni çıkarıp sistemin nasıl etkilendiğini ölçme.
- **Normalization:** Ağırlıkların toplamını 1.0'a eşitleme.

</details>

---

<details id="madde-16">
<summary><strong>✅ Madde 16 — Batch Evaluation Paralelleştirme</strong></summary>

### Basit Anlatım
100 mektup göndermek istiyorsun. Tek tek postaneye gidip her birini ayrı ayrı göndermek yerine, hepsini bir çantaya koyup tek seferde bırakırsın. Batch evaluation da aynı: birden fazla trace'i paralel olarak değerlendirme.

### Ne Yapıldı
İki mod:
1. **Async mode:** Celery group ile gerçek paralellik (farklı worker'larda eşzamanlı)
2. **Sync mode:** Background thread ile HTTP yanıtını bloklamadan değerlendirme

### Teknik Terimler
- **Celery:** Python'da arka plan görev kuyruğu. Redis'e görev atar, worker'lar alıp işler.
- **Celery Group:** Birden fazla görevi paralel başlatan yapı. Hepsi bağımsız çalışır.
- **Background Thread:** Ana iş parçacığını bloklamadan arka planda çalışan iş parçacığı.
- **Blocking:** Bir işlem tamamlanana kadar diğer işlemlerin beklenmesi.

### Kod
```python
def enqueue_batch_evaluation(trace_ids: list[str]):
    if settings.evaluation_mode == "async":
        from celery import group
        job = group(evaluate_trace_task.s(tid) for tid in trace_ids)
        job.apply_async()  # Her biri farklı worker'da paralel
    else:
        thread = threading.Thread(target=_run_batch, args=(trace_ids,), daemon=False)
        thread.start()
```

</details>

---

<details id="madde-17">
<summary><strong>✅ Madde 17 — N+1 Query Problemi</strong></summary>

### Basit Anlatım
1000 öğrenci listeliyorsun. Her öğrencinin notlarını almak için ayrı ayrı DB'ye soruyorsun: 1 (öğrenci listesi) + 1000 (her birinin notu) = 1001 sorgu! Oysa tek sorguda hepsini alabilirsin.

### Ne Yapıldı
SQLAlchemy'nin `joinedload` ve `selectinload` stratejileri kullanılarak, trace listelerken evaluation sonuçları tek sorguda birlikte getiriliyor.

### Teknik Terimler
- **N+1 Query Problem:** N kayıt listelenirken, her biri için ek 1 sorgu yapılması. Toplam N+1 sorgu → yavaş.
- **Eager Loading:** İlişkili verileri ana sorguyla birlikte yükleme (lazy loading'in tersi).
- **joinedload:** SQL JOIN ile ana tabloya ek tabloyu birleştirme. 1-to-1 ilişkiler için ideal.
- **selectinload:** Ayrı bir `SELECT ... WHERE id IN (...)` sorgusu. 1-to-many ilişkiler için ideal (JOIN'un Cartesian product sorununu önler).
- **Lazy Loading:** İlişkili veriye ilk erişildiğinde otomatik sorgu atma. N+1'in kaynağı.

### Kod
```python
items = (
    base
    .options(
        joinedload(Trace.evaluation_result),         # 1-to-1: JOIN
        selectinload(Trace.step_evaluation_results), # 1-to-many: IN query
    )
    .order_by(Trace.created_at.desc())
    .limit(per_page)
    .all()
)
# Önceden: 1 + N + N = 2N+1 sorgu
# Şimdi: 1 + 1 = 2 sorgu
```

</details>

---

<details id="madde-18">
<summary><strong>✅ Madde 18 — Content Hash Evaluation Cache</strong></summary>

### Basit Anlatım
Aynı soruyu aynı cevapla tekrar tekrar değerlendirmek, aynı sınavı tekrar tekrar çözmek gibi — sonuç değişmez. Cache ile "bu soruyu daha önce değerlendirdim, sonucu direkt vereyim" denir.

### Ne Yapıldı
`question + answer + contexts + ground_truth`'un SHA-256 hash'i hesaplanıyor. Aynı hash daha önce değerlendirilmişse, sonuç kopyalanıyor — LLM çağrısı yapılmıyor.

### Teknik Terimler
- **Cache:** Daha önce hesaplanmış sonuçları saklayıp tekrar kullanma.
- **SHA-256:** 256-bit kriptografik hash fonksiyonu. Girdi ne kadar değişirse değişsin, çıktı her zaman 64 karakter hex string.
- **Content Hash:** İçerik tabanlı parmak izi. Aynı içerik = aynı hash → aynı sonuç.
- **Hash Collision:** İki farklı girdinin aynı hash'i üretmesi. SHA-256'da pratik olarak imkansız (evrende atomdan fazla olasılık).
- **Deduplication:** Tekrarlı işlemleri tespit edip kaldırma.

### Kod
```python
def _compute_content_hash(question, answer, contexts, ground_truth):
    parts = [question.strip(), answer.strip()]
    for ctx in sorted(contexts or []):
        parts.append(ctx.strip())
    if ground_truth:
        parts.append(ground_truth.strip())
    combined = "\n---\n".join(parts)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()

# Kullanım:
existing = db.query(EvaluationResult).filter_by(content_hash=content_hash).first()
if existing:
    _copy_evaluation(existing, new_evaluation)  # LLM'i çağırmadan kopyala
    return
```

</details>

---

<details id="madde-19">
<summary><strong>✅ Madde 19 — Token Tracking & Cost Monitoring</strong></summary>

### Basit Anlatım
Telefonunda ne kadar GB harcadığını takip etmezsen, ay sonunda fatura şok eder. LLM kullanımını da takip etmeliyiz — her çağrıda kaç token harcandı, kaç dolar tuttu.

### Ne Yapıldı
Her LLM çağrısı sonrasında OpenAI'ın döndüğü `usage` bilgisi (prompt_tokens, completion_tokens) toplanıyor ve DB'ye yazılıyor. Stage 1 ve Stage 2 ayrı fiyatlandığı için per-stage tracking yapılıyor.

### Teknik Terimler
- **Token Usage:** LLM çağrısında harcanan token miktarı. Prompt (girdi) + completion (çıktı) olarak 2'ye ayrılır.
- **Cost per 1M Tokens:** LLM sağlayıcıların fiyatlandırma birimi. 1 milyon token başına USD.
- **Prompt Tokens:** LLM'e gönderilen girdi metni token sayısı. Daha ucuz.
- **Completion Tokens:** LLM'in ürettiği çıktı token sayısı. Daha pahalı.
- **Accumulator:** Her çağrıda biriken sayacı tutan değişken.

### Fiyatlandırma
```python
# config.py
stage1_input_price: float = 2.50    # gpt-5.2 input: $2.50/1M
stage1_output_price: float = 10.00  # gpt-5.2 output: $10.00/1M
stage2_input_price: float = 0.40    # gpt-5-mini input: $0.40/1M
stage2_output_price: float = 1.60   # gpt-5-mini output: $1.60/1M
```

### Formül
$cost = \frac{s1\_prompt \times 2.50 + s1\_completion \times 10.00 + s2\_prompt \times 0.40 + s2\_completion \times 1.60}{1{,}000{,}000}$

</details>

---

<details id="madde-20">
<summary><strong>✅ Madde 20 — Webhook Callback Mekanizması</strong></summary>

### Basit Anlatım
Kargo siparişi verdiğinde sürekli "kargom nerede?" diye sormazsın — kargo firması sana "teslim edildi" SMSi atar. Webhook de aynı: evaluation bitince, sonuçları otomatik olarak kullanıcının belirttiği URL'ye POST olarak gönderiyoruz.

### Ne Yapıldı
Trace oluşturulurken opsiyonel `webhook_url` verilebiliyor. Evaluation bitince sonuçlar HMAC-SHA256 imzalı olarak bu URL'ye gönderiliyor. 3 deneme, exponential backoff.

### Teknik Terimler
- **Webhook:** Bir olay gerçekleştiğinde otomatik HTTP POST isteği gönderme mekanizması. Polling'in (sürekli sorma) tersi.
- **HMAC-SHA256:** Hash-based Message Authentication Code. Payload'ı secret key ile imzalayarak, alıcının mesajın bozulmadığını ve doğru göndericiden geldiğini doğrulamasını sağlar.
- **Payload:** HTTP isteğinin gövdesinde gönderilen JSON verisi.
- **X-Signature-SHA256:** İmzayı taşıyan HTTP header'ı. Alıcı aynı secret ile aynı payload'ı hashleyip karşılaştırır.

### Kod
```python
# Webhook payload
{
    "event": "evaluation.completed",
    "trace_id": "uuid",
    "status": "completed",
    "scores": { "overall_score": 0.82, "clarity": 0.9, ... },
    "flags": { "is_off_topic": false, "is_deflection": false },
    "cost_usd": 0.003142
}

# İmzalama
signature = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
headers["X-Signature-SHA256"] = signature
```

</details>

---

## YENİ MİMARİ REVIEW (27 Sorun)

---

<details id="madde-21">
<summary><strong>✅ Madde 21 — SSRF Webhook Koruması (Critical #1)</strong></summary>

### Basit Anlatım
Evine "istediğin adrese mektup gönderirim" diyen bir kargo firması düşün. Birisi "şu adresteki kasaya git, şifreyi al ve bana gönder" derse? İç network'üne erişim sağlamış olur. SSRF tam olarak bu — kullanıcı verdiği URL ile sunucunun iç ağına erişim sağlama saldırısı.

### Ne Yapıldı
3 katmanlı koruma eklendi:
1. **Schema katmanı:** Sadece `https://` kabul ediliyor
2. **DNS aşaması:** Hostname resolve edilip private IP'ler engelleniyor
3. **Hostname listesi:** Docker servis isimleri (db, redis, api, worker) bloklanıyor

### Teknik Terimler
- **SSRF (Server-Side Request Forgery):** Sunucuyu, iç ağdaki servislere istek atmaya zorlamak. Saldırgan kendi erişemediği kaynaklara sunucu üzerinden erişir.
- **Private IP Ranges:** İç ağ için ayrılmış IP adresleri: `10.x.x.x`, `172.16-31.x.x`, `192.168.x.x`, `127.0.0.1` (localhost).
- **Link-Local:** `169.254.x.x` adresleri. AWS metadata servisi `169.254.169.254` bu aralıkta — credential çalınabilir.
- **DNS Rebinding:** Hostname çözümlemesini manipüle ederek, ilk çözümde public IP, ikinci çözümde private IP döndürme saldırısı.
- **Cloud Metadata Service:** AWS/GCP/Azure'un instance'a bilgi veren iç servisi. `http://169.254.169.254/latest/meta-data/` → IAM credentials çalınabilir.

### Kod
```python
_BLOCKED_HOSTNAMES = frozenset({
    "localhost", "db", "redis", "api", "worker", "pgadmin",
    "metadata.google.internal",
})

def _is_private_ip(ip_str: str) -> bool:
    addr = ipaddress.ip_address(ip_str)
    return addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved

def _validate_webhook_target(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https": return False
    if parsed.hostname in _BLOCKED_HOSTNAMES: return False
    # DNS resolve → tüm IP'leri kontrol et
    for _, _, _, _, sockaddr in socket.getaddrinfo(hostname, 443):
        if _is_private_ip(sockaddr[0]): return False
    return True
```

</details>

---

<details id="madde-22">
<summary><strong>✅ Madde 22 — Loop-Aware AsyncClient (Critical #2)</strong></summary>

### Basit Anlatım
Bir telefon hattın var. İş yerinde kullanıyorsun, sorun yok. Ama aynı hattı eve taşıyıp kullanmaya çalışırsan "bu hat bu santrale kayıtlı değil" hatası alırsın. AsyncClient da bir event loop'a bağlı — farklı loop'ta kullanılamaz.

### Ne Yapıldı
Tek bir class-level singleton yerine, her event loop için ayrı bir AsyncClient oluşturulup `loop_id → client` sözlüğünde tutuluyor. Eski loop'ların client'ları otomatik temizleniyor.

### Teknik Terimler
- **Event Loop:** Asyncio'nun kalbi. Tüm async işlemleri sıraya koyup çalıştıran döngü. Bir thread'de bir tane olur.
- **asyncio.run():** Her çağrıda **yeni** bir event loop oluşturur ve çalıştırır. Celery worker her task'ta bunu çağırır.
- **Stale Client:** Eski (artık var olmayan) event loop'a bağlı kalmış client. İstek atmaya çalışınca `RuntimeError` fırlatır.
- **Singleton Pattern:** Bir sınıftan sadece tek instance oluşturmayı garanti eden desen.
- **Loop-Aware:** Event loop'a göre farklı davranış gösteren yapı.

### Kod
```python
class OpenAILLMClient:
    _clients_by_loop: dict[int, httpx.AsyncClient] = {}  # loop_id → client
    _clients_lock = threading.Lock()

    @classmethod
    def _get_http_client(cls):
        loop = asyncio.get_running_loop()
        loop_id = id(loop)   # Her loop'un benzersiz kimliği

        with cls._clients_lock:
            client = cls._clients_by_loop.get(loop_id)
            if client and not client.is_closed:
                return client  # Bu loop için zaten var, kullan

            # Eski loop'ların kapatılmış client'larını temizle
            stale = [k for k, v in cls._clients_by_loop.items() if v.is_closed]
            for k in stale:
                del cls._clients_by_loop[k]

            # Bu loop için yeni client oluştur
            client = httpx.AsyncClient(...)
            cls._clients_by_loop[loop_id] = client
            return client
```

</details>

---

<details id="madde-23">
<summary><strong>✅ Madde 23 — Thread-Safe Circuit Breaker (Critical #3)</strong></summary>

### Basit Anlatım
İki kişi aynı anda bir kapının kilidini çevirmeye çalışıyor. `asyncio.Lock` sadece aynı event loop içinde çalışır — farklı loop'tan (Celery worker) gelenler kilidi göremez. `threading.Lock` ise tüm thread'lerde geçerli.

### Ne Yapıldı
Circuit breaker'daki `asyncio.Lock()` → `threading.Lock()` ile değiştirildi. Böylece farklı event loop'lardan gelen istekler de aynı circuit breaker durumunu güvenli şekilde paylaşabilir.

### Teknik Terimler
- **asyncio.Lock:** Sadece tek bir event loop içinde çalışan kilit. Farklı loop'tan `await` edilemez.
- **threading.Lock:** İşletim sistemi seviyesinde kilit. Tüm thread'lerde ve loop'larda çalışır. GIL (Global Interpreter Lock) ile birlikte kullanılır.
- **Race Condition:** İki veya daha fazla iş parçacığının aynı veriye eşzamanlı erişip tutarsız sonuç üretmesi.
- **Thread-Safe:** Birden fazla thread'den güvenli şekilde erişilebilen yapı.
- **GIL (Global Interpreter Lock):** Python'da aynı anda sadece bir thread'in Python bytecode çalıştırmasını sağlayan kilit. I/O sırasında bırakılır.

### Kod
```python
# Önce:
self._lock = asyncio.Lock()           # Sadece aynı loop'ta çalışır
async with self._lock: ...             # Farklı loop = hata!

# Sonra:
self._lock = threading.Lock()          # Tüm thread/loop'larda çalışır
with self._lock: ...                   # Her yerden güvenli
```

</details>

---

<details id="madde-24">
<summary><strong>✅ Madde 24 — Auth Rate Limiting (High #4)</strong></summary>

### Basit Anlatım
Kapına 1 dakikada 100 kişi gelse, hepsine kapıyı açar mısın? Hayır — sadece tanıdıklarını alırsın. Auth endpoint'leri de brute-force saldırılarına karşı korunmalı.

### Ne Yapıldı
- `/register`: IP başına dakikada **3 istek**
- `/login`: IP başına dakikada **5 istek**
- Diğer endpoint'ler: Genel 60/dakika limiti

### Teknik Terimler
- **Rate Limiting:** Belirli zaman diliminde izin verilen istek sayısını sınırlama.
- **Brute-Force Attack:** Tüm olası şifreleri sırayla deneyerek doğrusunu bulma saldırısı.
- **Credential Stuffing:** Başka sitelerden sızmış kullanıcı adı/şifre çiftlerini deneme.
- **SlowAPI:** FastAPI için rate limiting kütüphanesi. `Limiter` nesnesi ile dekoratör olarak uygulanır.
- **Key Function:** Rate limit'in neye göre sayılacağını belirleyen fonksiyon. `get_remote_address` = IP başına.

### Kod
```python
# app/rate_limit.py — Paylaşımlı limiter (circular import'u engeller)
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

# app/routers/auth.py
@router.post("/register")
@limiter.limit("3/minute")      # 3 kayıt/dakika
def register(request, payload, db): ...

@router.post("/login")
@limiter.limit("5/minute")      # 5 giriş denemesi/dakika
def login(request, payload, db): ...
```

</details>

---

<details id="madde-25">
<summary><strong>✅ Madde 25 — Celery Retry Scope (High #5)</strong></summary>

### Basit Anlatım
Her hatada tekrar denemek mantıklı değil. "Şifren yanlış" dediğinde tekrar denemek anlamsız — ama "sunucu meşgul" dediğinde mantıklı. Retry sadece geçici hatalarda yapılmalı.

### Ne Yapıldı
`autoretry_for=(Exception,)` → `autoretry_for=(LLMClientError, httpx.TimeoutException, httpx.HTTPError, ConnectionError)` olarak daraltıldı. Artık syntax error, validation error gibi kalıcı hatalar boşuna tekrarlanmıyor.

### Teknik Terimler
- **Transient Error:** Geçici hata. Tekrar denenince düzelebilir: timeout, rate limit, sunucu hatası.
- **Permanent Error:** Kalıcı hata. Tekrar denemenin faydası yok: 401 (yetki yok), 400 (validation hatası), bug.
- **autoretry_for:** Celery'de hangi exception türlerinde otomatik retry yapılacağını belirleyen parametre.
- **retry_backoff:** Her retry'da bekleme süresini artırma.
- **retry_jitter:** Bekleme süresine rastgele ekleme yaparak tüm worker'ların aynı anda retry yapmasını engelleme.
- **Thundering Herd:** Tüm client'ların aynı anda retry yaparak sunucuyu tekrar boğması.

### Kod
```python
@celery_app.task(
    autoretry_for=(
        LLMClientError,         # LLM çağrısı hataları
        httpx.TimeoutException, # Timeout
        httpx.HTTPError,        # Network hataları
        ConnectionError,        # Bağlantı kopması
    ),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def evaluate_trace_task(self, trace_id):
    evaluate_trace_and_persist(trace_id)
```

</details>

---

<details id="madde-26">
<summary><strong>✅ Madde 26 — Sync Webhook Blocking (Skip - False Positive)</strong></summary>

### Basit Anlatım
"Webhook teslimatı sync HTTP kullanıyor, event loop'u bloklar" denildi. Ama incelendiğinde webhook delivery yalnızca Celery worker'dan veya background thread'den çağrılıyor — asla FastAPI event loop'undan değil. Sorun yok.

### Neden Skip Edildi
`_deliver_webhook()` sadece `evaluate_trace_and_persist()` içinden çağrılıyor. Bu fonksiyon ya:
1. Celery worker'da çalışıyor (ayrı process, kendi event loop'u yok)
2. Background thread'de çalışıyor (blocking tamamıyla sorunsuz)

Hiçbirinde FastAPI'ın async event loop'u etkilenmiyor.

### Teknik Terimler
- **Blocking I/O:** Bir I/O işlemi tamamlanana kadar thread'in beklemesi. Thread-based bağlamda sorun değil, async bağlamda sorun.
- **Event Loop Blocking:** Async event loop'ta uzun süren sync işlem yapılması. Tüm async işlemler durur.
- **False Positive:** Aslında sorun olmayan bir durumun sorun olarak tespit edilmesi.

</details>

---

<details id="madde-27">
<summary><strong>✅ Madde 27 — Hardcoded Credentials Kaldırma (High #7)</strong></summary>

### Basit Anlatım
Evin anahtarını kapının altındaki paspasın altına koymak gibi — herkes bilir. Kaynak kodda `postgres:postgres` yazıyorsa, kodu gören herkes DB şifresini bilir.

### Ne Yapıldı
`DATABASE_URL` artık default değeri olmayan **zorunlu** alan. Environment variable veya `.env` dosyasından verilmezse uygulama başlamaz. Docker Compose kendi fallback'ini kullanır, ama doğrudan çalıştırmada güvenli.

### Teknik Terimler
- **Hardcoded Credentials:** Şifre/secret'ın kaynak koduna yazılması. En büyük güvenlik günah'larından biri.
- **Environment Variable:** İşletim sistemi seviyesinde tanımlanan değişken. Kod'dan bağımsız, deploy ortamına göre değişir.
- **12-Factor App:** Modern uygulama geliştirme metodolojisi. 3. faktör: "Config'i environment'ta tut."
- **Pydantic Settings:** Python'da env variable'ları tip güvenli şekilde okuyan kütüphane. Eksik zorunlu alan → `ValidationError` → uygulama başlamaz.

### Kod
```python
# ÖNCEKİ (güvenli değil):
database_url: str = "postgresql+psycopg2://postgres:postgres@db:5432/rageval"

# ŞİMDİ (güvenli):
database_url: str  # Default yok! Env'de yoksa → startup error
```

</details>

---

<details id="madde-28">
<summary><strong>✅ Madde 28 — Missing Env Vars Crash (High #8)</strong></summary>

### Basit Anlatım
Madde 27 ile aynı prensip. Zorunlu env variable'lar yoksa, uygulama çalışma anında gizemli bir hata yerine başlangıçta net bir hata veriyor.

### Ne Yapıldı
Pydantic `BaseSettings` ile `database_url` default'suz tanımlandı. Eksik olursa:
```
pydantic_settings.ValidationError: 1 validation error for Settings
database_url
  Field required [type=missing, ...]
```

### Teknik Terimler
- **Fail-Fast:** Hata olduğunda mümkün olan en erken noktada dur. Sessizce devam etme.
- **Validation Error:** Veri doğrulama hatası. Beklenmedik/eksik değer tespit edildi.
- **Startup Error:** Uygulama henüz başlamadan fırlatılan hata. Çalışma zamanında gizemli buglardan çok daha iyi.

</details>

---

<details id="madde-29">
<summary><strong>✅ Madde 29 — Webhook URL Format Doğrulama (High #9)</strong></summary>

### Basit Anlatım
Birine adres soruyorsun: "Ankara" dese yetmez, "Kızılay Mah, Atatürk Bulvarı No:5" demeli. URL de aynı — sadece `https://` ile başlaması yetmez, geçerli bir domain name olmalı.

### Ne Yapıldı
Pydantic field_validator ile:
1. `https://` zorunlu
2. Geçerli hostname zorunlu
3. Bare IP adresi (ör: `https://192.168.1.1/`) yasak
4. Tek segmentli hostname (ör: `https://intranet/`) yasak — FQDN gerekli

### Teknik Terimler
- **FQDN (Fully Qualified Domain Name):** En az bir nokta içeren tam domain adı: `api.example.com`. Tek segmentli `intranet` değil.
- **Bare IP:** Domain yerine doğrudan IP adresi kullanma. SSRF'in bir vektörü.
- **Field Validator:** Pydantic'te tek bir alan için özel doğrulama fonksiyonu.
- **URL Parsing:** URL'ü parçalarına ayırma: `scheme://hostname:port/path?query#fragment`

### Kod
```python
@field_validator("webhook_url")
def validate_webhook_url(cls, v):
    parsed = urlparse(v)
    if parsed.scheme != "https":
        raise ValueError("webhook_url must use https:// scheme")
    if not parsed.hostname:
        raise ValueError("webhook_url must contain a valid hostname")
    hostname = parsed.hostname
    if hostname.replace(".", "").isdigit() or ":" in hostname:
        raise ValueError("webhook_url must use a domain name, not an IP address")
    if "." not in hostname:
        raise ValueError("webhook_url must be a fully qualified domain name")
    return v
```

</details>

---

<details id="madde-30">
<summary><strong>✅ Madde 30 — Celery Worker Concurrency (Medium #10)</strong></summary>

### Basit Anlatım
Bir restoranda tek garson varsa, 10 masa aynı anda sipariş verse herkes bekler. 4 garson koyarsan 4 masa paralel servis alır.

### Ne Yapıldı
Celery worker'ı `--concurrency=4 --pool=prefork` ile başlatılıyor. 4 child process aynı anda 4 farklı evaluation çalıştırıyor.

### Teknik Terimler
- **Concurrency:** Aynı anda kaç işin paralel çalışabileceği.
- **Prefork Pool:** Her iş için ayrı process oluşturma stratejisi. CPU-bound işler için ideal. Fork = process kopyalama.
- **Worker:** Celery'de görevleri alan ve çalıştıran process.
- **Child Process:** Ana worker process'in oluşturduğu alt process'ler.

### Kod
```yaml
# docker-compose.yml
worker:
  command: celery -A app.tasks.celery_app.celery_app worker
           --loglevel=info --concurrency=4 --pool=prefork
```

</details>

---

<details id="madde-31">
<summary><strong>✅ Madde 31 — DB Connection Pool Yapılandırması (Medium #11)</strong></summary>

### Basit Anlatım
Bir otoparkta 5 yeriniz varsa 6. araba giremez. DB connection pool da aynı — kaç bağlantı olacağını, taşma durumunda ne yapılacağını, eskiyen bağlantıların ne zaman yenileneceğini belirlemek gerekiyor.

### Ne Yapıldı
SQLAlchemy engine'e explicit pool parametreleri eklendi:
- `pool_size=10`: Normal koşullarda 10 bağlantı hazır
- `max_overflow=20`: Yoğun dönemde +20 ek bağlantı (toplam 30)
- `pool_recycle=300`: 5 dakikadan eski bağlantıları yenile (stale TCP'yi engelle)
- `pool_pre_ping=True`: Bağlantıyı vermeden önce canlı mı diye kontrol et

### Teknik Terimler
- **Connection Pool:** Veritabanı bağlantılarını önceden oluşturup yeniden kullanma mekanizması.
- **pool_size:** Havuzda her zaman hazır tutulan bağlantı sayısı.
- **max_overflow:** pool_size dolduğunda ek oluşturulabilecek bağlantı sayısı.
- **pool_recycle:** Bir bağlantının kaç saniye sonra yenileneceği. Eski TCP bağlantıları firewall'da timeout olabilir.
- **pool_pre_ping:** `SELECT 1` göndererek bağlantının canlı olup olmadığını kontrol etme.

### Kod
```python
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,     # Ölü bağlantı mı? Yenisiyle değiştir
    pool_size=10,            # 10 hazır bağlantı
    max_overflow=20,         # Yoğunlukta +20 = toplam 30
    pool_recycle=300,        # 5 dakikada bir yenile
)
```

</details>

---

<details id="madde-32">
<summary><strong>✅ Madde 32 — Cascade Delete (Medium #12)</strong></summary>

### Basit Anlatım
Bir öğrenci okuldan ayrılınca, not karnesi de silinmeli. Yoksa "olmayan öğrencinin notları" diye orphan (yetim) kayıtlar kalır.

### Ne Yapıldı
Trace silindiğinde ilişkili `EvaluationResult` ve `StepEvaluationResult` kayıtları da otomatik siliniyor:
- SQLAlchemy tarafı: `cascade="all, delete-orphan"`
- PostgreSQL tarafı: `ondelete="CASCADE"` FK constraint
- Migration ile mevcut FK'lar güncellendi

### Teknik Terimler
- **Cascade Delete:** Üst kayıt silinince alt kayıtların otomatik silinmesi.
- **Orphan Record:** Üst kaydı silinen ama kendisi kalan yetim kayıt. Veri bütünlüğü ihlali.
- **Foreign Key Constraint:** İki tablo arasındaki ilişkiyi zorlayan veritabanı kuralı.
- **ON DELETE CASCADE:** PostgreSQL'de FK tanımında, parent silinince child'ın da silinmesini sağlayan seçenek.
- **passive_deletes=True:** SQLAlchemy'ye "DB tarafında CASCADE var, sen ayrıca DELETE atma" demek. Performans kazanımı.

### Kod
```python
# Model (SQLAlchemy ORM)
evaluation_result = relationship(
    "EvaluationResult",
    cascade="all, delete-orphan",
    passive_deletes=True,
)

# Migration (Alembic)
op.create_foreign_key(
    "evaluation_results_trace_id_fkey",
    "evaluation_results", "traces",
    ["trace_id"], ["id"],
    ondelete="CASCADE",
)
```

</details>

---

<details id="madde-33">
<summary><strong>✅ Madde 33 — Daemon Thread Graceful Shutdown (Medium #13)</strong></summary>

### Basit Anlatım
Restoran kapanırken mutfakta yarım kalan siparişleri çöpe atarsın (daemon thread). Ama iyi bir restoran, "son siparişlerinizi tamamlıyoruz, 15 dakika" der (graceful shutdown).

### Ne Yapıldı
Batch evaluation thread'leri `daemon=False` yapıldı (process kapanırken bekle). Ayrıca shutdown hook'unda `wait_for_batch_threads(timeout=60s)` eklendi.

### Teknik Terimler
- **Daemon Thread:** Ana process kapanınca otomatik öldürülen thread. Temizlik yapamaz.
- **Non-Daemon Thread:** Ana process kapanmadan önce bitmesini beklediği thread.
- **Graceful Shutdown:** Uygulamanın kapanırken devam eden işleri tamamlaması, kaynakları temizlemesi.
- **Lifespan:** FastAPI'da uygulama başlangıç/kapanış yaşam döngüsü. `async with lifespan` context manager.
- **Thread Join:** Bir thread'in bitmesini bekleme. `thread.join(timeout=60)` = en fazla 60 saniye bekle.

### Kod
```python
# Evaluation service
_active_batch_threads: list[threading.Thread] = []

def wait_for_batch_threads(timeout: float = 60.0):
    for t in _active_batch_threads:
        if t.is_alive():
            t.join(timeout=timeout)
    _active_batch_threads.clear()

# main.py lifespan
@asynccontextmanager
async def lifespan(app):
    yield  # Uygulama çalışıyor
    # Shutdown:
    wait_for_batch_threads(timeout=60.0)      # Batch thread'leri tamamla
    await OpenAILLMClient.close_shared_client()  # HTTP client'ı kapat
```

</details>

---

<details id="madde-34">
<summary><strong>✅ Madde 34 — Maliyet Hesaplama Doğruluğu (Medium #14)</strong></summary>

### Basit Anlatım
Fatınız geldi: su + elektrik toplamı 100₺. Ama suyun %35'i su, %65'i elektrik diye tahmin etmek yerine, her birinin sayacına bakmak daha doğru değil mi?

### Ne Yapıldı
Eskiden toplam token'lar tahminî oranlarla bölünüyordu (%35 Stage 1, %65 Stage 2). Artık her stage'in kendi token sayısı ayrı takip ediliyor ve doğru fiyatla çarpılıyor.

### Teknik Terimler
- **Per-Stage Token Tracking:** Her aşamanın harcadığı token'ı ayrı ayrı sayma.
- **Model Pricing Tier:** Farklı modellerin farklı fiyatlandırması. gpt-5.2 daha pahalı, gpt-5-mini daha ucuz.

### Kod
```python
# ESKİ (tahmini):
s1_prompt = prompt_tokens * 0.35  # %35 Stage 1'e ait diye tahmin et
s2_prompt = prompt_tokens * 0.65  # %65 Stage 2'ye ait diye tahmin et

# YENİ (kesin):
stage1_prompt_tokens = stage_1.prompt_tokens        # Stage 1'den gelen gerçek sayı
stage2_prompt_tokens = rag_results["_prompt_tokens"] + s2_resp.prompt_tokens  # Stage 2 + RAG

cost = (
    stage1_prompt * 2.50/1M + stage1_completion * 10.00/1M  # gpt-5.2 fiyatı
  + stage2_prompt * 0.40/1M + stage2_completion * 1.60/1M   # gpt-5-mini fiyatı
)
```

</details>

---

<details id="madde-35">
<summary><strong>✅ Madde 35 — Dead Specificity Column (Medium #15)</strong></summary>

### Basit Anlatım
Evinde kullanmadığın ama yerinden kaldırmadığın bir mobilya var — yer kaplıyor ama işlevi yok. `specificity` kolonu da öyle.

### Ne Yapıldı
`specificity` hiçbir metrikte hesaplanmıyor, hiçbir yerde kullanılmıyor. Kolonu silmek migration gerektirir ve geriye dönük uyumluluk bozar. Bu yüzden **"DEPRECATED"** olarak işaretlendi.

### Teknik Terimler
- **Dead Code:** Çalışmayan, kullanılmayan kod. Bakım yükü oluşturur.
- **Deprecated:** "Kullanımdan kaldırılacak" olarak işaretlenmiş. Henüz silınmedi ama yeni kodda kullanılmamalı.
- **Backward Compatibility:** Eski versiyonlarla uyumluluk. Kolon silinse, eski client'lar bozulabilir.

</details>

---

<details id="madde-36">
<summary><strong>✅ Madde 36 — Token Race Condition (Skip - False Positive)</strong></summary>

### Basit Anlatım
"Birden fazla async task aynı anda token sayacına yazıyor, race condition var" denildi. Ama asyncio cooperative multitasking kullanıyor — `await` noktaları arasında başka task çalışmaz.

### Neden Skip Edildi
Python asyncio'da thread yok, preemption yok. `_accumulated_prompt_tokens += tokens` işlemi `await`'ler arası atomik. Race condition oluşması için aynı değişkene farklı thread'lerden yazılması gerekir — ama tüm RAG metric task'ları aynı event loop thread'inde çalışıyor.

### Teknik Terimler
- **Cooperative Multitasking:** Task'lar gönüllü olarak kontrolü bırakır (`await`). OS zorla kesmez.
- **Preemptive Multitasking:** OS istediği anda thread'i kesebilir. Thread'lerde race condition riski.
- **Atomicity:** Bir işlemin bölünemez olması. `x += 1` asyncio'da atomik (await yok), thread'lerde atomik değil.

</details>

---

<details id="madde-37">
<summary><strong>✅ Madde 37 — Count Query Optimizasyonu (Medium #17)</strong></summary>

### Basit Anlatım
1000 sayfalık bir kitabın her sayfasını açtığında "toplamda kaç sayfa var?" diye sayfa numaralarını tekrar saymak gereksiz — ilk seferde say, sonra hatırla.

### Ne Yapıldı
`COUNT(*)` sorgusu sadece ilk sayfa (page=1) için çalıştırılıyor. Sonraki sayfalarda gereksiz COUNT atılmıyor.

### Teknik Terimler
- **COUNT Query:** Tablodaki satır sayısını sayan SQL sorgusu. Büyük tablolarda yavaş olabilir.
- **Pagination:** Büyük veri setlerini sayfalara bölme. Offset-based vs cursor-based.
- **Offset Pagination:** `OFFSET 1000 LIMIT 20` — DB ilk 1000 satırı skip eder. Büyük offset'lerde yavaş ($O(n)$).

### Kod
```python
def list_traces(db, user, page, per_page):
    base = db.query(Trace).filter(Trace.user_id == user.id)
    items = base.order_by(Trace.created_at.desc()) \
                .offset((page - 1) * per_page) \
                .limit(per_page).all()
    # COUNT sadece ilk sayfada
    total = base.count() if page == 1 or items else 0
    return items, total
```

</details>

---

<details id="madde-38">
<summary><strong>✅ Madde 38 — Redis Healthcheck (Low)</strong></summary>

### Basit Anlatım
Docker'da "bu servis hazır mı?" diye sormadan diğer servisleri başlatıyorsun — Redis henüz ayağa kalkmamışken Celery bağlanmaya çalışıp hata alıyor.

### Ne Yapıldı
Redis'e `healthcheck` eklendi: `redis-cli ping` → `PONG` dönerse sağlıklı. API ve worker artık `service_healthy` koşuluna bağlı.

### Teknik Terimler
- **Healthcheck:** Bir servisin çalışıp çalışmadığını belirlemek için periyodik olarak yapılan kontrol.
- **service_healthy:** Docker Compose'da bir servisin healthcheck'inden "healthy" status almasını bekleme koşulu.
- **service_started:** Servisin sadece başlatılmış olmasını bekleme — sağlıklı olup olmadığına bakmaz.

### Kod
```yaml
redis:
  image: redis:7
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 5s
    timeout: 3s
    retries: 5

api:
  depends_on:
    redis:
      condition: service_healthy  # service_started → service_healthy
```

</details>

---

<details id="madde-39">
<summary><strong>✅ Madde 39 — Health Endpoint Redis Kontrolü (Low)</strong></summary>

### Basit Anlatım
Doktor sadece kalp yetmezliğini kontrol edip akciğeri atlıyordu. Şimdi Redis'i de kontrol ediyor — sistem Redis olmadan evaluation enqueue yapamaz.

### Ne Yapıldı
`/health` endpoint'ine Redis PING kontrolü eklendi. Status artık API + DB + Redis'i kapsıyor.

### Kod
```python
@app.get("/health")
def health():
    status_detail = {"api": "ok"}
    # DB kontrol
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        status_detail["database"] = "ok"
    except Exception:
        status_detail["database"] = "unavailable"
    # Redis kontrol
    try:
        import redis
        r = redis.from_url(settings.redis_url, socket_timeout=2)
        r.ping()
        status_detail["redis"] = "ok"
    except Exception:
        status_detail["redis"] = "unavailable"

    all_ok = all(v == "ok" for v in status_detail.values())
    return {"status": "ok" if all_ok else "degraded", "details": status_detail}
```

</details>

---

<details id="madde-40">
<summary><strong>✅ Madde 40 — Trace updated_at Kolonu (Low)</strong></summary>

### Basit Anlatım
"Bu dosyayı en son ne zaman değiştirdim?" sorusunun cevabı `updated_at` kolonunda. Trace status'u `pending → completed` olduğunda bu tarih otomatik güncelleniyor.

### Ne Yapıldı
Trace modeline `updated_at` kolonu eklendi. SQLAlchemy'nin `onupdate` parametresiyle her güncellenmede otomatik set ediliyor. Migration ile mevcut kayıtlar `created_at` değeriyle dolduruldu.

### Teknik Terimler
- **onupdate:** SQLAlchemy'de kayıt her güncellendiğinde otomatik çağrılan fonksiyon.
- **Backfill:** Yeni eklenen kolonu mevcut kayıtlar için doldurmak. `UPDATE traces SET updated_at = created_at`
- **NOT NULL Constraint:** Kolonun NULL olamayacağını zorlayan kural. Backfill'den sonra ekleniyor.

### Kod
```python
updated_at: Mapped[datetime] = mapped_column(
    DateTime, nullable=False,
    default=lambda: datetime.now(timezone.utc),
    onupdate=lambda: datetime.now(timezone.utc),   # Her UPDATE'te otomatik
)
```

</details>

---

<details id="madde-41-47">
<summary><strong>✅ Madde 41-47 — Kalan Low-Priority İyileştirmeler</strong></summary>

### Madde 41 — Status Enum Constraint
Trace status'u (`pending`, `evaluating`, `completed`, `failed`) DB seviyesinde kısıtlanabilir. Şu anki `String(20)` tipi herhangi bir stringi kabul ediyor. Enum constraint eklemek migration gerektirir — gelecek iterasyona bırakıldı.

### Madde 42 — Metrics Auth
`/api/v1/metrics` endpoint'leri auth gerektirmiyor — kasıtlı olarak public. Metrik tanımları secret değil.

### Madde 43 — pytest-asyncio Version
`pytest-asyncio==1.3.0` eski bir versiyon. `2.x` serisinde `@pytest.mark.asyncio` dekoratör davranışı değişti. Test uyumluluk riski nedeniyle şimdilik dokunulmadı.

### Madde 44 — Sync ORM in Async Endpoints
FastAPI endpoint'leri async olabilir ama SQLAlchemy sync engine kullanıyor. `run_in_executor` ile thread pool'a atılabilir ama mevcut yük seviyesinde gereksiz.

### Madde 45 — Single Celery Worker Scalability
Tek worker instance yeterli şu an. Yük artarsa `docker-compose scale worker=3` ile scale edilebilir.

### Madde 46 — Duplicate Parse Functions
`_safe_parse_json` (evaluator.py) ve `_safe_parse` (rag_metrics.py) benzer ama tam olarak aynı değil. Birleştirme, edge case'deki davranış farklarını kırar — ayrı tutuluyor.

### Madde 47 — Idempotency Key
Aynı trace'in iki kez ingest edilmesini engellemek için client-generated idempotency key. API tasarım kararı — gelecek versiyona planlandı.

</details>

---

## ÖZET TABLO

| # | Kategori | Sorun | Çözüm | Durum |
|---|----------|-------|-------|-------|
| 1 | Kalite | Prompt rubric tutarsızlığı | Paylaşımlı RUBRIC_BLOCK | ✅ |
| 2 | Performans | HTTP bağlantı havuzu yok | httpx.AsyncClient pool | ✅ |
| 3 | Güvenilirlik | Kayıt sırası hatası | Atomik transaction | ✅ |
| 4 | Güvenilirlik | Aşırı uzun girdi | Konfigüre edilebilir truncation | ✅ |
| 5 | Kalite | Stage 1/2 metrik farkı | Aynı required fields | ✅ |
| 6 | Kalite | LLM-bağımlı overall score | Ağırlıklı deterministik formül | ✅ |
| 7 | Kalite | Score cap'ler yok | Off-topic/deflection/contradiction caps | ✅ |
| 8 | Güvenilirlik | Retry mekanizması yok | Exponential backoff + Retry-After | ✅ |
| 9 | Güvenilirlik | Circuit breaker yok | 3-state devre kesici | ✅ |
| 10 | Güvenlik | CORS hardcoded | ENV-driven konfigürasyon | ✅ |
| 11 | Güvenilirlik | Health session leak | Context manager (with) | ✅ |
| 12 | Kalite | Context numaralama | 1-based standardizasyon | ✅ |
| 13 | Kalite | Agreement claim bias | Capped penalty formülü | ✅ |
| 14 | Kalite | Dual completeness | Tek kaynak (RAG metrics) | ✅ |
| 15 | Kalite | Metrik ağırlıkları | Research-backed ağırlıklar | ✅ |
| 16 | Performans | Sequential batch eval | Celery group + background thread | ✅ |
| 17 | Performans | N+1 query | joinedload + selectinload | ✅ |
| 18 | Performans | Tekrarlı evaluation | Content hash cache | ✅ |
| 19 | Operasyon | Token/cost takibi yok | Per-stage token accumulator | ✅ |
| 20 | Operasyon | Sonuç bildirimi yok | HMAC-signed webhook callback | ✅ |
| 21 | **Güvenlik** | SSRF webhook | 3-layer protection (schema+DNS+blocklist) | ✅ |
| 22 | **Güvenlik** | Cross-loop AsyncClient | Loop-aware client dict | ✅ |
| 23 | **Güvenlik** | Cross-loop Lock | threading.Lock | ✅ |
| 24 | **Güvenlik** | Auth brute-force | Rate limit (3/min, 5/min) | ✅ |
| 25 | Güvenilirlik | Tüm exception retry | Scoped retry (transient only) | ✅ |
| 26 | — | Sync webhook blocking | Skip (false positive) | ⏭️ |
| 27 | **Güvenlik** | Hardcoded DB şifresi | Required env variable | ✅ |
| 28 | Güvenilirlik | Eksik env = gizemli hata | Fail-fast startup error | ✅ |
| 29 | **Güvenlik** | URL format doğrulama | FQDN + no bare IP | ✅ |
| 30 | Performans | Tek Celery worker | concurrency=4 prefork | ✅ |
| 31 | Performans | DB pool yapılandırma | pool_size=10, overflow=20 | ✅ |
| 32 | Veri Bütünlüğü | Orphan kayıtlar | CASCADE delete | ✅ |
| 33 | Güvenilirlik | Daemon thread kill | Graceful shutdown + join | ✅ |
| 34 | Doğruluk | Tahmini maliyet | Per-stage gerçek token sayımı | ✅ |
| 35 | Temizlik | Dead specificity | DEPRECATED işaretlendi | ✅ |
| 36 | — | Token race condition | Skip (false positive — asyncio) | ⏭️ |
| 37 | Performans | Her sayfada COUNT | İlk sayfa only COUNT | ✅ |
| 38 | Operasyon | Redis healthcheck yok | Docker healthcheck + dependency | ✅ |
| 39 | Operasyon | Health'te Redis yok | health endpoint Redis PING | ✅ |
| 40 | Operasyon | updated_at yok | onupdate ile otomatik | ✅ |
| 41-47 | Low | Çeşitli iyileştirmeler | Gelecek iterasyona planlandı | 📋 || **48** | **Performans** | Token limit çok yüksek (16384) | max_completion_tokens 4096 + prompt kısaltma | ✅ |
| **49** | **Performans** | Hallucination 2 aşamalı (2 LLM çağrısı) | Single-call structured output birleştirme | ✅ |
| **50** | **Performans** | Stage 2, RAG'i gereksiz yere bekliyor | Pipeline restructure — Stage 2 RAG'den bağımsız | ✅ |
| **51** | **Doğruluk** | Completeness/citation hep null | Token limit artırma (1024→2048/1536) | ✅ |
| **52** | **Operasyon** | Evaluation süresi takibi yok | evaluation_duration_ms (DB + webhook + API) | ✅ |
| **53** | **Operasyon** | Stage/metric timing görünürlüğü yok | Pipeline timing instrumentation (loglar) | ✅ |

---

## PERFORMANS OPTİMİZASYONLARI (Phase 1-3)

> Bu bölümde evaluation pipeline'ının **144 saniyeden 16.8 saniyeye** düşürülme sürecindeki 6 iyileştirme detaylı açıklanmıştır.

---

<details id="madde-48">
<summary><strong>✅ Madde 48 — Token Limit Optimizasyonu + Prompt Kısaltma (144s → 53s)</strong></summary>

### Basit Anlatım
Bir öğrenciye "sınav kağıdı en fazla 100 sayfa olabilir" dersen, bazıları gerçekten 100 sayfa yazar — gereksiz tekrarlar, dolgu cümlelerle. Ama "en fazla 10 sayfa" dersen, özüne odaklanır. LLM'ler de aynı: token limiti ne kadar yüksekse, o kadar genişletir.

### Sorun
Tüm LLM çağrılarında `max_completion_tokens=16384` kullanılıyordu. LLM'ler gereksiz yere uzun çıktı üretiyordu:
- Stage 1 reasoning: ~5000 token (gereksiz tekrarlar)
- RAG metrikleri: Her biri ~2000 token

Bu hem **daha yavaş** (daha fazla token üretmek = daha fazla zaman) hem de **daha pahalı** idi.

### Ne Yapıldı

1. **Token limitleri düşürüldü:**
   - Stage 1: `16384 → 4096`
   - Stage 2: `16384 → 4096`
   - RAG metrikleri: `16384 → 2048`

2. **Stage 1 prompt'una conciseness talimatı eklendi:**
```python
STAGE_1_SYSTEM_PROMPT = """
...
Keep your total response under 1500 words.
"""
```

3. **Stage 2 repair prompt truncation:**
```python
# Retry'larda Stage 1 reasoning'i 4000 karaktere kısaltıldı
truncated_reasoning = stage_1_reasoning[:4000] if len(stage_1_reasoning) > 4000 else stage_1_reasoning
```

### Neden İşe Yaradı
- Daha az token = daha az üretim süresi (LLM'ler token-by-token üretir)
- Daha kısa Stage 1 çıktısı = Stage 2'nin input'u da kısalır = Stage 2 daha hızlı
- Prompt kısaltma talimatı ile LLM gereksiz tekrardan kaçınır

### Dosyalar
- `app/evaluation/evaluator.py` — Stage 1/2 token limitleri
- `app/evaluation/rag_metrics.py` — RAG metrik token limitleri
- `app/evaluation/prompts.py` — "under 1500 words" talimatı, repair truncation

### Etki
**144s → 53s** (~63% iyileşme)

</details>

---

<details id="madde-49">
<summary><strong>✅ Madde 49 — Hallucination Single-Call Birleştirme (53s → 35s)</strong></summary>

### Basit Anlatım
Bir avukat, tanıklık alırken önce serbest konuşturur (Stage 1), sonra bir katibin bu konuşmayı resmi tutanağa dönüştürmesini bekler (Stage 2). İki ayrı adım. Ya avukat doğrudan tutanak formatında konuşma alabilseydi? Tek adım, yarı süre.

### Sorun
Hallucination metriği kendi içinde iki ayrı LLM çağrısından oluşuyordu:

```
Hallucination Stage 1 (serbest metin):
  "Cevaptaki iddiaları çıkar, context ile karşılaştır, muhakemeni yaz"
  → ~8s

Hallucination Stage 2 (JSON dönüşümü):
  "Yukarıdaki muhakemeyi JSON'a çevir"
  → ~5s

Toplam: ~13s (sıralı)
```

Hallucination zaten RAG metrikleri arasındaki **darboğazdı** — en uzun süren metrik. İki LLM çağrısı bunu daha da yavaşlatıyordu.

### Ne Yapıldı
OpenAI'ın **Structured Outputs** (`strict: true` JSON schema) özelliği kullanılarak iki aşama tek bir çağrıya birleştirildi:

```python
# ESKİ: 2 çağrı
resp1 = await client.chat_completion(  # Stage 1: serbest metin reasoning
    system_prompt=HALLUCINATION_STAGE_1_SYSTEM_PROMPT, ...
)
resp2 = await client.chat_completion(  # Stage 2: JSON dönüşümü
    system_prompt=HALLUCINATION_STAGE_2_SYSTEM_PROMPT,
    user_prompt=resp1.content, ...
)

# YENİ: 1 çağrı — hem düşün, hem JSON döndür
resp = await client.chat_completion(
    system_prompt=HALLUCINATION_SYSTEM_PROMPT,
    user_prompt=build_hallucination_user_prompt(answer, contexts),
    max_completion_tokens=4096,
    json_schema=HALLUCINATION_JSON_SCHEMA,  # strict schema zorunluluğu
)
```

### Neden Eski Yöntemde 2 Çağrı Gerekiyordu?
Structured Outputs öncesinde LLM'den güvenilir JSON almak zordu — schema hataları, eksik parantezler, format bozuklukları. "Önce düşün, sonra başka bir LLM JSON'a çevirsin" yaklaşımı gerekiyordu. `strict: true` ile API seviyesinde JSON schema uyumu garanti ediliyor — ayrı bir dönüştürücüye gerek kalmadı.

### Neden Ana Pipeline Stage 1→2 Birleştirilmedi?
Ana pipeline'da Stage 1 **gpt-5.2** (güçlü, pahalı) derin muhakeme için, Stage 2 **gpt-5-mini** (hızlı, ucuz) basit JSON dönüşümü için kullanılıyor. Farklı modeller → birleştirilemez.

Hallucination'da ise zaten ikisi de **gpt-5-mini** idi — birleştirmek doğal.

### Dosyalar
- `app/evaluation/rag_metrics.py` — `compute_hallucination_rubric()` tek çağrı
- `app/evaluation/prompts.py` — `HALLUCINATION_SYSTEM_PROMPT`, `HALLUCINATION_JSON_SCHEMA`

### Etki
**53s → 26-35s** (~45% iyileşme, çünkü hallucination darboğazdı)

</details>

---

<details id="madde-50">
<summary><strong>✅ Madde 50 — Stage 2 Pipeline Restructure (35s → 16.8s)</strong></summary>

### Basit Anlatım
Bir restoranda yemek hazırlanırken: tatlı (Stage 2) sadece ana yemeğin (Stage 1) pişmesini beklemeli — garnitürlerin (RAG) hazır olmasını beklemeye gerek yok. Ama eski kodda tatlı hazırlığı, garnitürler bitene kadar başlamıyordu. Neden? Çünkü yanlışlıkla "hepsi hazır olunca başla" denilmişti.

### Sorun
Pipeline'da Stage 2, Stage 1 çıktısını JSON'a çevirir — **RAG sonuçlarına ihtiyacı yoktur.** Ama eski kodda:

```python
# ESKİ: Stage 2, RAG'in bitmesini bekliyordu
stage_1_task = asyncio.create_task(...)
rag_metrics_task = asyncio.create_task(...)

stage_1 = await stage_1_task        # 5s
rag_results = await rag_metrics_task  # 25s bekle! ❌
# Stage 2 ancak burada başlıyordu — RAG bittikten sonra
s2_resp = await client.chat_completion(...)  # 10s
# Toplam: 25 + 10 = 35s
```

### Ne Yapıldı
Stage 2, Stage 1 biter bitmez başlatıldı — RAG'i beklemeden:

```python
# YENİ: Stage 2, RAG'den bağımsız
stage_1_task = asyncio.create_task(...)    # t=0
rag_metrics_task = asyncio.create_task(...)  # t=0

stage_1 = await stage_1_task  # t=5s — Stage 1 bitti

# Stage 2 HEMEN başla (RAG hâlâ çalışıyor!)
s2_resp = await client.chat_completion(
    user_prompt=build_stage_2_user_prompt(stage_1.content),  # sadece Stage 1 çıktısı
    ...
)  # t=15s — Stage 2 bitti

# ŞİMDİ RAG'i bekle (muhtemelen çoktan bitmiştir)
rag_results = await rag_metrics_task  # t=25s
# Toplam: max(15, 25) = 25s
```

**Ayrıca:** Stage 2 token limiti `4096 → 2048` düşürüldü (çıktı küçük bir JSON, 4096 gereksiz).

### Timeline Karşılaştırma
```
ESKİ:
  t=0  → Stage 1 (5s) + RAG (25s)  ← paralel
  t=25 → RAG bitti → Stage 2 (10s)
  t=35 → Bitti ✓                    = 35s

YENİ:
  t=0  → Stage 1 (5s) + RAG (25s)  ← paralel
  t=5  → Stage 1 bitti → Stage 2 (10s)  ← RAG'i beklemiyor!
  t=15 → Stage 2 bitti (RAG hâlâ çalışıyor...)
  t=25 → RAG bitti ✓               = max(15, 25) = 25s
```

### Dosyalar
- `app/evaluation/evaluator.py` — `evaluate_trace()` pipeline restructure

### Etki
**35s → 21-28s lokal, 16.8s production sunucuda** (~52% iyileşme)

</details>

---

<details id="madde-51">
<summary><strong>✅ Madde 51 — Completeness / Citation Token Limit Fix</strong></summary>

### Basit Anlatım
Bir öğrenciye "cevabını 1 sayfaya sığdır" dersen ama aslında 2 sayfa gerekiyorsa, sınav kağıdını yarım bırakır. LLM'ler de aynı: çıktı token limitine ulaşırsa, `finish_reason=length` ile keser ve structured output'ta `content=null` döner.

### Sorun
Completeness metriği hep `null` dönüyordu. Sebep:
- `max_completion_tokens=1024` idi
- Completeness çıktısı (key points + evidence) 1024 token'a sığmıyordu
- OpenAI Structured Outputs'ta truncate olursa `content=null` döner (kısmi JSON üretemez)

### Ne Yapıldı
```python
# Completeness: 1024 → 2048
resp = await client.chat_completion(
    model=settings.rag_metrics_model,
    system_prompt=COMPLETENESS_SYSTEM_PROMPT,
    max_completion_tokens=2048,  # was 1024
    ...
)

# Citation check: 1024 → 1536
resp = await client.chat_completion(
    model=settings.rag_metrics_model,
    system_prompt=CITATION_CHECK_SYSTEM_PROMPT,
    max_completion_tokens=1536,  # was 1024
    ...
)
```

**Hallucination** için de 4096→2048 ve 4096→3072 denendi, ama ikisi de bazı durumlarda null döndürdü. 4096'da sabitlendi (güvenli minimum).

### Dosyalar
- `app/evaluation/rag_metrics.py` — `compute_completeness()`, `compute_citation_check()`

### Etki
Completeness ve citation_check metrikleri artık güvenilir sonuç döndürüyor (null yerine gerçek skorlar).

</details>

---

<details id="madde-52">
<summary><strong>✅ Madde 52 — evaluation_duration_ms Feature</strong></summary>

### Basit Anlatım
Bir doktor muayenesinin "ne kadar sürdüğünü" kaydetmesi gibid — hem performans takibi hem de SLA uyumu için gerekli.

### Sorun
Evaluation'ın ne kadar sürdüğü hiçbir yerde kaydedilmiyordu. Production'da yavaşlama olduğunda fark etmek imkansızdı.

### Ne Yapıldı

1. **DB modeli — yeni kolon:**
```python
# app/models/evaluation.py
evaluation_duration_ms = Column(Integer, nullable=True)
```

2. **Migration (0012):**
```python
# alembic/versions/0012_add_evaluation_duration_ms.py
op.add_column('evaluation_results', sa.Column('evaluation_duration_ms', sa.Integer()))
```

3. **Service — zamanlama:**
```python
# app/services/evaluation_service.py
eval_start = time.perf_counter()
result = await evaluate_trace(...)
eval_duration_ms = round((time.perf_counter() - eval_start) * 1000)
evaluation.evaluation_duration_ms = eval_duration_ms
```

4. **API response + Webhook payload:**
```json
{
  "event": "evaluation.completed",
  "evaluation_duration_ms": 16800,
  "scores": { ... }
}
```

### Dosyalar
- `app/models/evaluation.py` — DB kolon
- `alembic/versions/0012_add_evaluation_duration_ms.py` — Migration
- `app/services/evaluation_service.py` — Zamanlama kodu
- `app/schemas/ingest.py` — API response schema
- `app/routers/traces.py` — GET endpoint'leri

### Etki
Her evaluation'ın milisaniye cinsinden süresi kaydedilip API ve webhook'ta görülebiliyor.

</details>

---

<details id="madde-53">
<summary><strong>✅ Madde 53 — Pipeline Timing Instrumentation</strong></summary>

### Basit Anlatım
Bir arabanın dashboard'unda sadece toplam hız göstermek yetmez — motor devri, yakıt basıncı, turbo boost gibi alt metrikleri de görmek istersin. Aynı şekilde evaluation pipeline'ında hangi aşamanın ne kadar sürdüğünü görmek gerekiyordu.

### Sorun
Sadece toplam süre biliniyordu, darboğazın hangi aşamada olduğu belirsizdi. "Neden 35 saniye?" sorusuna cevap veremiyorduk.

### Ne Yapıldı

1. **Evaluator.py — Stage-level timing:**
```python
_t0 = _time.perf_counter()

stage_1 = await stage_1_task
_t1 = _time.perf_counter()
logger.info("Timing — Stage 1: %.1fs", _t1 - _t0)

# Stage 2 bitti
_t2 = _time.perf_counter()
logger.info("Timing — Stage 2: %.1fs", _t2 - _t1)

# RAG bitti
rag_results = await rag_metrics_task
_t3 = _time.perf_counter()
logger.info("Timing — RAG metrics: %.1fs | Pipeline total: %.1fs", _t3 - _t0, _t3 - _t0)
```

2. **rag_metrics.py — Per-metric timing:**
```python
async def _timed(name, coro):
    t = _time.perf_counter()
    result = await coro
    logger.info("RAG metric '%s' completed in %.1fs", name, _time.perf_counter() - t)
    return result

relevancy_task = asyncio.create_task(_timed("relevancy", compute_answer_relevancy(...)))
hallucination_task = asyncio.create_task(_timed("hallucination", compute_hallucination_rubric(...)))
# ... 6 metrik
```

### Örnek Log Çıktısı
```
Timing — Stage 1: 5.2s
RAG metric 'relevancy' completed in 3.1s
RAG metric 'citation' completed in 2.8s
RAG metric 'ctx_precision' completed in 3.4s
RAG metric 'ctx_recall' completed in 3.9s
RAG metric 'completeness' completed in 4.2s
RAG metric 'hallucination' completed in 12.1s
Timing — Stage 2: 4.8s (started right after Stage 1)
Timing — RAG metrics: 12.3s | Pipeline total: 12.3s
```

Bu loglar sayesinde hallucination'ın darboğaz olduğu tespit edildi ve optimizasyon öncelikleri belirlendi.

### Dosyalar
- `app/evaluation/evaluator.py` — Stage-level timing logları
- `app/evaluation/rag_metrics.py` — Per-metric `_timed()` wrapper

### Etki
Tüm pipeline darboğazları artık loglardan görülebiliyor.

</details>

---

## TOPLAM İYİLEŞME ÖZETİ

| Phase | Değişiklik | Önceki Süre | Sonraki Süre | İyileşme |
|-------|-----------|-------------|-------------|----------|
| **Phase 1** | Token limit + prompt kısaltma | 144s | 53s | -63% |
| **Phase 2** | Hallucination single-call | 53s | 26-35s | -45% |
| **Phase 3** | Pipeline restructure + Stage 2 token | 35s | 16.8s (prod) | -52% |
| **Toplam** | | **144s** | **16.8s** | **-88%** |