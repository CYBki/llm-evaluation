# RAG Eval Tool - Proje Ozeti

## Ne Yapiyoruz?

RAG sistemleri icin otomatik kalite olcum platformu. Kullanicilar SDK ile 3 satir kod ekliyor, her soru-cevap-context etkilesimi otomatik puanlaniyor.

---

## Nasil Calisiyor?

```
Kullanici RAG Sistemi → SDK (3 satir kod) → API'miz → Two-Stage LLM Puanlama → Dashboard'da Goster
```

1. Kullanici SDK'yi RAG sistemine entegre eder (3 satir)
2. Her soru + cevap + context otomatik olarak API'ye gonderilir
3. **Stage 1**: gpt-4o-mini rubric (puanlama cetveli) kullanarak serbest metin muhakeme uretir (Rubric-based CoT)
4. **Stage 2**: gpt-3.5-turbo muhakemeyi yapilandirilmis JSON skorlara donusturur
5. Sonuclar + aciklamalar dashboard'da gorsellenir

**Entegrasyon Ornegi:**

```python
from rageval import RagEvalTracker                          # ← 1. satir
tracker = RagEvalTracker()                                   # ← 2. satir (OPENAI_API_KEY + RAGEVAL_API_KEY env'den okunur)

def chat(question: str) -> str:
    contexts = retriever.search(question)
    answer = llm.generate(question, contexts)
    tracker.log(question=question, answer=answer, contexts=contexts)  # ← 3. satir
    return answer
```

**API Key Modeli:** Gelistirici zaten kullandigi `OPENAI_API_KEY`'i aynen kullanmaya devam eder (eval icin ekstra key gerekmez). `RAGEVAL_API_KEY` sadece bizim platforma auth icin gerekir.

---

## Rubric (Puanlama Cetveli) Nasil Belirleniyor?

Rubric = LLM'e "bu cevap iyi mi kotu mu" sorusunu **nasil cevaplayacagini** ogrettigimiz kurallar. Stage 1 prompt'unun icine gomulur.

**Ornek (completeness metrigi):**
- 1.0 = Sorudaki tum alt sorular eksiksiz cevaplanmis
- 0.7 = Buyuk kismi cevaplanmis, 1-2 nokta eksik
- 0.4 = Sadece bir kismi cevaplanmis
- 0.0 = Soruyla ilgisiz veya bos

**Rubric'i kim belirliyor?** Ekip yazıyor, LLM sadece uyguluyor.

**Ilham kaynaklari:**

| Metrik | Kaynak |
|---|---|
| completeness | RAGAS frameworku |
| coherence | G-Eval yaklasimi |
| helpfulness | RLHF reward modelleri |
| disagreement_claims | Datadog Hallucination Detection (claim bazli dogrulama) |

**Rubric evrimi (4 adim):**
1. **Taslak** — Literatur + domain bilgisiyle ilk cetveller yazilir
2. **Kalibrasyon** — Golden set (50-100 trace) uzerinde insan-LLM uyumu olculur (Cohen's Kappa ≥ 0.7 hedef)
3. **A/B Test** — v1 vs v2 karsilastirilir, kazanan uretim rubric'i olur
4. **Surekli iyilestirme** — Dusuk confidence trace'ler ekip tarafindan incelenir, rubric guncellenir

**Onemli:** Rubric evrimi ekip-gudumlududur, otonom degil. Kullanici geri bildirimi (thumbs up/down) rubric'i dogrudan degistirmez, sadece ekibin nereye bakmasi gerektigini gosterir.

Her evaluation sonucunda `rubric_version` saklanir (v1.0, v1.1, v2.0...), eski puanlamalarin hangi cetvel ile yapildigi bilinir.

---

## Hallucination Tespiti

Ayri bir model/pipeline yok — Stage 1 rubric'inin parcasi olarak calisir.

**Mantik:** Cevaptaki her faktuel iddia (claim) context'le karsilastirilir:

| Kategori | Anlami | Ornek |
|---|---|---|
| **supported** | Context destekliyor ✅ | "Mobil uygulamadan talep" → Context: "mobil uygulama veya sube" |
| **contradiction** | Context celiskili bilgi veriyor ❌ | "24 saat icinde" → Context: "3 is gunu icinde" |
| **missing_info** | Context bu konuda bilgi icermiyor ⚠️ | "6 ay musteri sarti"ndan bahsetmemis |
| **fabricated** | Context'te hic olmayan detay uydurulmus ❌ | "Faiz orani %1.5" (context'te faizden soz yok) |

Sonuc `disagreement_claims` olarak JSON'da doner ve dashboard'da gosterilir.

| Teknoloji | Ne Icin | Neden Bu |
|---|---|---|
| **FastAPI** | Backend API | Async destegi, otomatik Swagger, Python ekosistemi, hizli gelistirme |
| **PostgreSQL** | Veritabani | Guclu JSON destegi, guvenilir, ucretsiz, buyuk veri icin uygun |
| **SQLAlchemy 2.0** | ORM (DB erisim katmani) | Python'da standart, migration destegi (Alembic), tip guvenligi |
| **Pydantic v2** | Veri dogrulama | FastAPI ile entegre, otomatik validation, hizli |
| **OpenAI gpt-4o-mini + gpt-3.5-turbo** | Two-Stage Rubric-based LLM-as-Judge | Stage 1: gpt-4o-mini (rubric + CoT muhakeme), Stage 2: gpt-3.5-turbo (JSON formatlama). ~$0.00035/trace |
| **Redis** | Mesaj kuyrugu (Hafta 2) | Celery ile entegre, hizli, hafif, async islem icin ideal |
| **Celery** | Arka plan islem (Hafta 2) | Async eval, retry, toplu isleme, Python standart cozum |
| **sentence-transformers** | Embedding (Hafta 2) | answer_relevancy metrigi icin, ucretsiz, yerel calisir |
| **Next.js 14** | Frontend dashboard (Hafta 4) | App Router, SSR, React ekosistemi, hizli UI gelistirme |
| **Tailwind + shadcn/ui** | UI tasarim (Hafta 4) | Hazir bilesenler, tutarli tasarim, hizli prototipleme |
| **Recharts** | Grafikler (Hafta 4) | React ile uyumlu, kolay kullanim, ihtiyaca yeterli |
| **Docker Compose** | Deploy ve gelistirme | Tek komutla tum servisleri ayaga kaldir, ortam tutarliligi |
| **pytest + httpx** | Test | Python standart, async test destegi, FastAPI ile uyumlu |

---

## 4 Haftalik Plan

### Hafta 1 - Altyapi

Bu hafta projenin temeli atiliyor. Hicbir ozellik olmadan once sistemin ayaga kalkmasi gerekiyor.

| Yapilacak | Aciklama | Neden |
|---|---|---|
| **API + Veritabani kurulumu** | FastAPI projesi olusturulur, PostgreSQL baglantisi yapilir, Docker Compose ile ikisi birlikte calisir hale getirilir. User, Trace, EvaluationResult tablolari olusturulur. | Her sey bunun ustune insa edilecek. Veritabani olmadan veri saklayamayiz, API olmadan disariyla konusamayiz. |
| **Kullanici kaydi + API key** | Kullanici email+sifre ile kayit olur, sistem ona benzersiz bir API key uretir. Bu key SHA-256 ile hashlenerek DB'de saklanir. | Her kullanicinin kendi verisi izole olmali. API key sayesinde kim trace gonderiyor bilinir, yetkisiz erisim engellenir. |
| **Trace gonderme ve listeleme** | POST /ingest ile tek trace, POST /ingest/batch ile toplu trace gonderilir. GET /traces ile listelenir. Trace = bir soru + cevap + context bilgisi. | Bu projenin ana girdisi trace'dir. Kullanicinin RAG sisteminden gelen her soru + cevap + context bir trace olarak kaydedilir. |
| **8 metrikle LLM puanlama** | Two-stage Rubric-based CoT evaluation: Stage 1'de gpt-4o-mini her metrik icin puanlama cetvelini (rubric) kullanarak serbest metin muhakeme uretir. Stage 2'de gpt-3.5-turbo bu muhakemeyi yapilandirilmis JSON skorlara + reasoning_summary + disagreement_claims donusturur. | Rubric sayesinde LLM tutarli puanlar verir (0.7 mi 0.8 mi belirsizligi kalkar). Iki adimda ayrı yapmak daha derin analiz ve aciklanabilir sonuc verir. Kullanici neden o puani aldigini gorur. |
| **Testler** | Unit test (her servis ayri test edilir) ve integration test (kayit ol -> trace gonder -> puanla -> sonuc kontrol) yazilir. | Kodun dogru calistigindan emin olmamiz lazim. Sonraki haftalarda bir sey bozulursa testler yakalar. |

Hafta sonu: `docker-compose up` ile sistem ayaga kalkiyor, trace gonderiliyor, puanlaniyor.

---

### Hafta 2 - Gelismis Metrikler

Ilk haftada 8 temel metrik vardi. Bu hafta RAG'a ozel 5 yeni metrik ekleniyor ve puanlama arka plana tasiniyor.

| Yapilacak | Aciklama | Neden |
|---|---|---|
| **Redis + Celery ile async isleme** | Hafta 1'de trace gelince puanlama aninda yapiliyordu (kullanici bekliyordu). Simdi trace kabul edilir, kullaniciya "aldim" denir, puanlama arka planda Celery worker ile yapilir. | Puanlama 3-5 saniye surebilir. Kullaniciyi bekletmek kotu deneyim. Async ile trace'i aninda kabul edip arka planda degerlendirebiliriz. |
| **Answer Relevancy metrigi** | Soru ve cevabin ne kadar iliskili oldugunu olcer. sentence-transformers ile ikisinin embedding vektorleri cikarilir, cosine similarity hesaplanir. | LLM cagrisi gerektirmez, hizlidir. Cevabin soruyla alakali olup olmadigini matematiksel olarak olcer. |
| **Faithfulness metrigi** | Cevaptaki her iddia (claim) cikarilir, her birinin context'te olup olmadigi kontrol edilir. Skor = dogrulanan / toplam iddia. | RAG'in en kritik metrigi. Cevap context'e dayaniyor mu yoksa LLM uydurmus mu bunu olcer. |
| **Hallucination metrigi** | Faithfulness'in tersi gibi. Context'te olmayan uydurma iddialari tespit eder. | Kullanici yanlis bilgi almamali. Halusinasyon orani yuksekse RAG sistemi guvenilmez demektir. |
| **Citation Check metrigi** | Cevaptaki kaynak referanslarinin (citation tag) gercekten context'te olup olmadigini kontrol eder. | Bazi RAG sistemleri "[Kaynak 1]" gibi referans gosterir. Bunlarin gercek olup olmadigini dogrular. |
| **Dosya upload ile toplu degerlendirme (opsiyonel)** | CSV veya JSON dosya yukle, icindeki tum trace'ler otomatik Celery ile toplu degerlendirilir. | Kullanicinin biriktirdigi veriyi tek seferde yuklemesi icin. Manuel tek tek gondermek yerine toplu islem. Oncelik durumuna gore Sprint 2 veya sonraya ertelenebilir. |
| **Retry mekanizmasi** | LLM cagrisi basarisiz olursa (timeout, rate limit) otomatik tekrar dener. | LLM API'leri bazen basarisiz olur. Retry ile veri kaybi onlenir, her trace mutlaka degerlendirilir. |

Hafta sonu: 13 metrik calisiyor, puanlama arka planda, dosya upload mumkun.

---

### Hafta 3 - Analytics + SDK + Deploy

Veri toplaniyor ve puanlaniyor ama kullanici bu veriyi analiz edemiyor. Bu hafta analiz endpointleri, SDK paketi ve deploy hazirlaniyor.

| Yapilacak | Aciklama | Neden |
|---|---|---|
| **Summary endpoint** | Belirli bir donem icin ozet: ortalama skor, toplam trace, deflection orani, kalite dagilimi. | Kullanici "son 7 gunde durumum nasil?" sorusuna tek bakista cevap almali. |
| **Trends endpoint** | Zaman bazli grafik verisi: gunluk/haftalik/aylik ortalama skorlarin degisimi. | Kalite yukseliyor mu dususyor mu gormek icin. Trend takibi olmadan iyilesme olculmez. |
| **Worst Traces endpoint** | En dusuk skorlu trace'lerin listesi. | Kullanici en kotuleri gorup sistemini duzeltebilmeli. En cok nereler sorunlu hemen gorunsun. |
| **Distribution endpoint** | Bir metrigin dagilimi (histogram verisi). Ornegin helpfulness skorlarinin %'si. | "Cevaplarimin cogu iyi mi kotu mu?" sorusuna cevap verir. Genel dagilimi gosterir. |
| **Deflections endpoint** | Savusturma yapilan sorularin konu bazli analizi. | Hangi konularda sistem cevap veremeyip savusturuyor bunu gosterir. |
| **Compare endpoint** | Iki donemi karsilastir (orn: bu hafta vs gecen hafta). | A/B karsilastirma. Yaptigi iyilestirmenin etkisini gormek icin. |
| **Python SDK** | `pip install rageval` ile PyPI'den kurulan paket. `tracker.log(question, answer, contexts)` ile trace gonderir. | Kullanicinin API detaylariyla ugrasmamasi icin. 3 satir kodla entegrasyon tamamlansin. |", "oldString": "| **Python SDK** | `pip install rageval` ile kurulan paket. `tracker.log(question, answer, contexts)` ile trace gonderir. | Kullanicinin API detaylariyla ugrasmamasi icin. 3 satir kodla entegrasyon tamamlansin. |
| **Production Docker deploy** | Multi-stage Dockerfile, gunicorn, healthcheck, .env.production. Tum servisler tek komutla ayaga kalkar. | Gelistirme ortami ile uretim ortami farkli. Production-ready bir deploy olmadan canli kullanilamaz. |
| **E2E testler + dokumantasyon** | Uc uca test: SDK ile trace gonder -> puanla -> analytics sorgula. README.md ile kurulum rehberi. | Tum akisin birlikte calistigini dogrular. Dokumantasyon olmadan baskasi projeyi kullanamaz. |

Hafta sonu: Backend tamamen hazir, SDK calisiyor, deploy edilebilir durumda.

---

### Hafta 4 - Dashboard

Tum veri backend'de hazir. Simdi bunu insanlarin gorebilecegi bir web arayuzune dokuyoruz.

| Yapilacak | Aciklama | Neden |
|---|---|---|
| **Login sayfasi** | API key ile giris. Kullanici key'ini girer, dashboard'a erisir. | Herkes sadece kendi verisini gormeli. Yetkilendirme sart. |
| **Overview sayfasi** | KPI kartlari (toplam trace, ort. skor, deflection rate) + trend grafigi. Tek bakista genel durum. | Kullanicinin ilk girdigi sayfa. "Durumum nasil?" sorusuna aninda cevap. |
| **Traces listesi** | Tablo halinde tum trace'ler: soru, cevap, skor, tarih. Arama, siralama, pagination. | Tekil trace'lere ulasip detaylarini inceleyebilmek icin. |
| **Trace detay sayfasi** | Tek trace'in tum metrikleri, soru, cevap, context, bar chart ile skor gosterimi. | Sorunlu bir trace'in tam olarak neresinin kotu oldugunu gormek icin. |
| **Analytics sayfasi** | Metrik dagilim grafikleri (histogram), tarih ve metrik filtreleri. | Genel veri analizi. Hangi metrikler iyi, hangileri kotu, dagilim nasil. |
| **Worst traces** | En dusuk skorlu trace'lerin tablosu. | Oncelikli olarak duzeltilmesi gereken trace'leri hizla bulmak icin. |
| **Donem karsilastirma** | Iki donemin yan yana grafigi. | Iyilestirme oncesi/sonrasi karsilastirma yapabilmek icin. |
| **Canli izleme (Live Feed)** | Son gelen trace'lerin canli akisi (her birkac saniyede guncellenir). | Canli sistemlerde anlk olarak neler oldugunu takip etmek icin. |
| **Responsive + Dark mode** | Mobil, tablet ve masaustu uyumu. Acik/koyu tema. | Her cihazdan rahatca kullanilabilmesi icin. |

Hafta sonu: Dashboard canli, tum proje tamamlandi.

---

## Metrikler (13 Adet)

**Soru Kalitesi:** clarity, specificity, is_off_topic

**Cevap Kalitesi:** completeness, coherence, helpfulness, is_deflection, overall_score

**RAG Kalitesi (Hafta 2):** answer_relevancy, faithfulness, hallucination, citation_check, deflection_rate

---

## Dis Bagimlilik

| Ihtiyac | Neden | Maliyet |
|---|---|---|
| OpenAI API Key (gelistiricinin mevcut key'i) | Two-stage Rubric-based LLM puanlama | ~$0.00035/trace (~$3.5/10K trace) |
| RAGEVAL_API_KEY (platformdan alinir) | Bizim API'ye auth | Ucretsiz |

Gelistiricinin zaten kullandigi `OPENAI_API_KEY` eval icin de kullanilir, ekstra key gerekmez.
Diger her sey (DB, Redis, API) ucretsiz ve yerel calisiyor.

---

## Cikti

Hafta 4 sonunda:
- ✅ Calisan API (14 endpoint)
- ✅ 13 metrikle otomatik puanlama
- ✅ Python SDK (`pip install rageval` — PyPI'de yayinlandi)
- ✅ Web dashboard (grafikler + canli izleme)
- ✅ Docker ile tek komutla deploy
