# Betula — Öğrenme Rehberi

Bu dosya, projede kullanılan teknolojileri **ne işe yaradıkları**, **projede nerede durdukları** ve
**araştırırken nelere bakman gerektiği** ile birlikte listeler. Amaç, projeyi yalnızca geliştirmek değil;
her parçanın neden orada olduğunu anlatabilecek seviyeye gelmek. Bu seviye makalede ve sunumda da gerekiyor.

---

## Nasıl çalışmalı? (Önerilen yöntem)

Yalnızca teori okumak çabuk unutulur. Her konu için şu 4 adımlı döngüyü kullan:

1. **Kavram (30–60 dk):** Aşağıdaki "araştır" maddelerini resmi dokümandan ya da iyi bir videodan öğren.
2. **Projede bul (15–30 dk):** "Projede nerede" bölümündeki dosyayı aç ve kavramın kodda nasıl göründüğünü takip et.
3. **Küçük deney (30 dk):** Projeden bağımsız, 20–30 satırlık bir deneme yap. Örneğin tek başına bir FAISS indeksi kur.
   Ya da projede küçük bir değişiklik yapıp testleri çalıştır (`python -m pytest`) ve neyin bozulduğunu gör.
4. **Kendine anlat (5 dk):** "Kendini test et" sorularını yazılı olarak, kendi cümlelerinle cevapla.
   Cevaplayamıyorsan 1. adıma dön.

> İpucu: Benimle (Claude) çalışırken "bunu yazmadan önce bana ne yapacağını açıkla" ya da
> "bu fonksiyonu satır satır anlat" diyebilirsin. Bazı küçük değişiklikleri önce sen yazmayı dene,
> sonra bana inceletirsin. Öğrenmenin en hızlı yolu bu.

**Önerilen sıra:** Katman 1 → 2 → 3 → 4 → 5 → 6. Her katman bir sonrakinin temelini oluşturuyor.
İşaretler: 🟢 temel (mutlaka) · 🟡 önemli · 🔵 ileri / makale için

---

## Katman 1 — Temeller

### 🟢 Python (ileri seviye özellikler)
- **Ne işe yarar:** Backend'in tamamı Python ile yazıldı.
- **Projede nerede:** Her yerde. Özellikle [research_graph.py](../backend/agents/research_graph.py) ve [chunking.py](../backend/services/chunking.py).
- **Araştır:**
  - Type hint'ler (`list[dict]`, `Optional`, `TypedDict`)
  - `dataclass`
  - Decorator'lar (`@lru_cache`, `@contextmanager`)
  - Generator ve `yield`: sohbetteki akışlı cevaplar bununla çalışır
  - Context manager (`with`)
  - Modül/paket yapısı ve `__init__.py`
  - Sanal ortam (venv, conda) ve `requirements.txt`
- **Kendini test et:**
  - `yield` kullanan bir fonksiyon ile `return` kullanan bir fonksiyon arasındaki fark nedir?
  - `get_settings()` neden `@lru_cache` ile işaretli?

### 🟢 Git ve GitHub
- **Ne işe yarar:** Sürüm kontrolü; neyin, ne zaman, neden değiştiğinin kaydını tutar.
- **Projede nerede:** `.gitignore`, commit geçmişi.
- **Araştır:** commit / push / pull, branch, `.gitignore`, `git rm --cached`, "git geçmişinde hassas veri" problemi, iyi commit mesajı nasıl yazılır.
- **Kendini test et:** Bir dosyayı `.gitignore`'a eklemek, o dosyayı geçmişten siler mi? Neden?

### 🟢 HTTP ve REST API kavramları
- **Ne işe yarar:** Tarayıcıdaki arayüz ile sunucu bu protokolle konuşur.
- **Araştır:**
  - GET / POST / PATCH / DELETE
  - Durum kodları (200, 400, 401, 404, 500)
  - Header (özellikle `Authorization` ve projede kullanılan `X-Session-Id`)
  - JSON
  - `multipart/form-data` (dosya yükleme bununla yapılır)
  - CORS
- **Kendini test et:** 401 ile 404 arasındaki fark nedir? Projede hangi durumda hangisi dönüyor?

---

## Katman 2 — Backend (sunucu)

### 🟢 FastAPI
- **Ne işe yarar:** Python ile hızlı web API'si yazmayı sağlayan framework. Projenin "kapısı".
- **Projede nerede:** [main.py](../backend/main.py), [backend/api/routers/](../backend/api/routers/)
- **Araştır:**
  - Router ve `APIRouter`
  - Path ve query parametreleri
  - **Dependency Injection (`Depends`)**: [deps.py](../backend/auth/deps.py) içindeki `CurrentUser` ve `CurrentSession` bununla çalışır
  - `lifespan` (açılış ve kapanış işleri)
  - `BackgroundTasks`: Master Sentez arka planda bununla çalışır
  - `StreamingResponse`
  - Otomatik dokümantasyon (`/docs` adresi)
- **Kendini test et:**
  - Bir istek `/documents/upload`'a geldiğinde kimlik kontrolü hangi sırayla, nerede yapılıyor?

### 🟢 Pydantic ve pydantic-settings
- **Ne işe yarar:** Veri doğrulama (gelen JSON doğru biçimde mi?) ve ayarların `.env` dosyasından okunması.
- **Projede nerede:** [schemas.py](../backend/schemas.py), [config.py](../backend/config.py)
- **Araştır:** `BaseModel`, `BaseSettings`, `field_validator`, response_model.
- **Kendini test et:** `.env` dosyasındaki bir değer ile ortam değişkeni çakışırsa hangisi kazanır?

### 🟢 SQLite ve SQL
- **Ne işe yarar:** Kullanıcılar, belgeler, oturumlar, quizler gibi kalıcı verilerin saklandığı veritabanı.
- **Projede nerede:** [db.py](../modules/db.py), `modules/repo_*.py`
- **Araştır:**
  - Temel SQL: SELECT, INSERT, UPDATE, JOIN, INDEX
  - Foreign key
  - **Parametreli sorgu (`?`) ve SQL injection**
  - Migration kavramı (projede `ALTER TABLE ... ADD COLUMN` ile elle yapılıyor)
  - SQLite'ın sınırları: aynı anda birden çok yazıcı olduğunda neler olur?
- **Kendini test et:** Sorguya kullanıcı girdisini neden f-string ile değil `?` ile koyuyoruz?

### 🟡 Repository Pattern ve katmanlı mimari
- **Ne işe yarar:** Veritabanı kodunu iş mantığından ayırır; kod düzenli ve test edilebilir olur.
- **Projede nerede:** `routers/` (HTTP) → `services/` (iş mantığı) → `modules/repo_*.py` (veri).
- **Araştır:** Layered architecture, Repository pattern, Separation of Concerns, modüler monolit ve mikroservis karşılaştırması.
- **Kendini test et:** Yarın SQLite yerine PostgreSQL'e geçmek istesen hangi dosyalar değişirdi?

### 🟡 Kimlik doğrulama: JWT, bcrypt, OAuth 2.0
- **Ne işe yarar:**
  - Kullanıcının kim olduğunu doğrulamak (JWT)
  - Şifreleri güvenli saklamak (bcrypt)
  - Google veya GitHub ile giriş (OAuth)
- **Projede nerede:** [jwt.py](../backend/auth/jwt.py), [auth.py](../modules/auth.py), [oauth.py](../backend/services/oauth.py)
- **Araştır:**
  - JWT'nin 3 parçası ve "imza" ne demek
  - Hash ile şifreleme farkı; salt
  - OAuth "authorization code flow"
  - `state` parametresi neden var?
- **Kendini test et:** JWT'nin içi neden herkes tarafından okunabilir, ama neden değiştirilemez?

### 🟡 Server-Sent Events (SSE)
- **Ne işe yarar:** Sohbet cevabının kelime kelime akarak gelmesi.
- **Projede nerede:** [chat.py](../backend/api/routers/chat.py) (`_sse`, `generate`), [api.js](../frontend/js/api.js)
- **Araştır:** SSE ve WebSocket karşılaştırması, `text/event-stream` biçimi, "polling" ile "push" farkı.
- **Kendini test et:** Master Sentez ilerlemesi şu an polling ile izleniyor. SSE'ye geçmek ne kazandırır?

---

## Katman 3 — Yapay zekâ çekirdeği (projenin kalbi)

### 🟢 LLM (Büyük Dil Modeli) temelleri
- **Ne işe yarar:** Sohbet, eksik analizi, sentez ve quiz üretimi.
- **Araştır:**
  - Token
  - **Context window** (model bir seferde ne kadar metin görebilir; projede 35–40 bin karakter sınırının nedeni bu)
  - Temperature
  - Halüsinasyon
  - Prompt engineering: rol verme, çıktıyı JSON'a zorlama, few-shot
  - Reasoning modelleri (ör. gpt-oss) ile klasik modeller arasındaki fark
- **Projede nerede:** `GAP_PROMPT` ve `SYNTHESIS_PROMPT` ([research_graph.py](../backend/agents/research_graph.py)), `_RAG_TEMPLATE` ([rag_engine.py](../modules/rag_engine.py))
- **Kendini test et:**
  - Eksik analizinde neden `temperature=0.1`, sentezde neden `0.3` kullanılıyor?

### 🟢 Groq (LLM sağlayıcısı)
- **Ne işe yarar:** Modelleri bulutta çok hızlı çalıştıran servis. Proje modeli kendi bilgisayarında değil, burada çalıştırıyor.
- **Projede nerede:** [groq.py](../backend/llm/groq.py)
- **Araştır:**
  - API anahtarı ve güvenliği
  - Rate limit, ücretsiz katman sınırları
  - Model kullanımdan kaldırma (deprecation). Llama modellerinin kaldırılmasıyla yaşadığımız sorun buydu.
  - Groq'u hızlı yapan şey: LPU
- **Kendini test et:** Model adını koda sabit yazmak yerine `.env`'den okumanın avantajı nedir?

### 🟢 LangChain
- **Ne işe yarar:** LLM, prompt, vektör veritabanı ve metin bölücü gibi parçaları birbirine bağlayan kütüphane.
- **Projede nerede:** `ChatPromptTemplate`, `prompt | llm` zinciri ([rag_engine.py](../modules/rag_engine.py)), `Document`, `RecursiveCharacterTextSplitter` ([chunking.py](../backend/services/chunking.py))
- **Araştır:**
  - LCEL (`|` operatörü)
  - `invoke` ve `stream` farkı
  - `Document` nesnesi (`page_content` + `metadata`)
  - **Callback'ler** (`BaseCallbackHandler`): her LLM çağrısının token ve süresi bununla loglanıyor; bkz. [telemetry.py](../backend/llm/telemetry.py)
- **Kendini test et:**
  - `chain.stream()` ile `chain.invoke()` farkı nedir? Sohbette hangisi neden kullanılıyor?
  - Telemetri neden çağrının yapıldığı yerde değil de bir callback içinde tutuluyor?

### 🟢 RAG (Retrieval-Augmented Generation)
- **Ne işe yarar:** Modelin senin belgeni "bilmesi" için önce ilgili parçaları bulup soruyla birlikte modele vermek. Projenin en önemli kavramı.
- **Projede nerede:** Yükleme → parçalama → embedding → FAISS → soru gelince benzer parçaları bul → prompt'a ekle → cevap. Akışı [chat.py](../backend/api/routers/chat.py) içindeki `_build_context_snippet` fonksiyonundan takip et.
- **Araştır:**
  - RAG mimarisi
  - **Chunking stratejileri**: parça boyutu, overlap, sayfa sınırı (Faz 0'da yaptığımız değişiklik)
  - Metadata ve kaynak gösterme (citation)
  - Hibrit arama (BM25 + vektör)
  - Reranker
  - RAG ile fine-tuning farkı
- **Kendini test et:**
  - Parçalar neden 750 karakter ve 150 karakter örtüşmeli?
  - Parçaların sayfa sınırını aşmaması neden önemli?

### 🟢 Embedding (vektör temsili) ve Sentence-Transformers
- **Ne işe yarar:** Metni sayılardan oluşan bir vektöre çevirir. Anlamca yakın metinlerin vektörleri de birbirine yakın olur.
- **Projede nerede:** [vectorstore.py](../backend/services/vectorstore.py), model: `paraphrase-multilingual-MiniLM-L12-v2`
- **Araştır:**
  - Kosinüs benzerliği
  - Embedding boyutu
  - Çok dilli modeller (Türkçe neden önemli?)
  - Hugging Face Hub
  - MTEB benchmark'ı (embedding modelleri nasıl karşılaştırılır)
  - Alternatif modeller: `bge-m3`, `multilingual-e5`
- **Kendini test et:** "Araba" ile "otomobil" kelimesinde hiç ortak harf yok. Embedding bunları nasıl yakın bulur?

### 🟢 FAISS (vektör veritabanı)
- **Ne işe yarar:** Milyonlarca vektör arasında en benzerleri çok hızlı bulur.
- **Projede nerede:** [vectorstore.py](../backend/services/vectorstore.py) (`index_chunks`, `load_vector_db`)
- **Araştır:**
  - Yakın komşu arama (k-NN)
  - Kesin arama ile yaklaşık arama (ANN) farkı
  - FAISS indeks türleri (Flat, IVF, HNSW)
  - Diske kaydetme (`save_local`)
  - Alternatifler: Chroma, Qdrant, pgvector
  - `allow_dangerous_deserialization` neden "tehlikeli"? (pickle güvenliği)
- **Kendini test et:** Bir belge yeniden derlendiğinde eski parçaları nasıl siliyoruz? (İpucu: id öneki `doc<id>:`)

### 🟢 LangGraph ve ajan (agent) mimarisi
- **Ne işe yarar:** Çok adımlı yapay zekâ iş akışlarını "düğüm" ve "kenar" içeren bir grafik olarak tanımlar.
- **Projede nerede:** [research_graph.py](../backend/agents/research_graph.py), akış: `parse → gap_analysis → web_research → synthesis → persist`
- **Araştır:**
  - StateGraph, node, edge, conditional edge
  - State (durum) yönetimi
  - Döngüler (ör. "yeterli değilse tekrar ara")
  - Agent ile chain arasındaki fark
  - ReAct, tool calling
  - Human-in-the-loop
- **Kendini test et:** Şu an akış düz bir çizgi. "Doğrulama başarısızsa web aramasına geri dön" adımını eklemek için ne gerekir?

### 🟡 Web araması (DuckDuckGo)
- **Ne işe yarar:** Belgede eksik olan konuları internetten tamamlamak.
- **Projede nerede:** `_ddg_search` ([research_graph.py](../backend/agents/research_graph.py), [enrichment.py](../backend/services/enrichment.py))
- **Araştır:** Arama API'leri (DuckDuckGo, Tavily, SerpAPI), kaynak güvenilirliği, paralel istek (`ThreadPoolExecutor`).
- **Kendini test et:** Web'den gelen yanlış bir bilginin nota girmesini nasıl engelleyebiliriz?

---

## Katman 4 — Belge işleme

### 🟢 PyMuPDF (fitz) ve python-docx
- **Ne işe yarar:** PDF ve Word dosyalarından metin çıkarmak, ayrıca PDF/DOCX dışa aktarma.
- **Projede nerede:** [documents.py](../backend/services/documents.py), [export_docs.py](../backend/services/export_docs.py)
- **Araştır:**
  - PDF'in iç yapısı (metin aslında "konumlu karakterler"dir)
  - `page.get_text()` modları ("text", "blocks", "dict")
  - Yazı tipi boyutundan başlık tespiti: projede `page.get_text("dict")` ile yapılıyor; bkz. `_mark_headings` ve [sections.py](../backend/services/sections.py)
  - `pymupdf4llm`
  - Taranmış PDF ve OCR (Tesseract)
- **Kendini test et:** Taranmış (fotoğraf) bir PDF yüklenirse şu an ne olur? Neden?

---

## Katman 5 — Arayüz (frontend)

### 🟡 HTML, CSS ve vanilla JavaScript
- **Ne işe yarar:** Kullanıcının gördüğü her şey.
- **Projede nerede:** [frontend/](../frontend/), özellikle [app.js](../frontend/js/app.js) ve [api.js](../frontend/js/api.js)
- **Araştır:**
  - DOM
  - `fetch` ve `async/await`
  - `localStorage` (token burada tutuluyor; XSS riski nedir?)
  - Akış (stream) okuma: `ReadableStream`
  - Olay dinleyicileri (event listener)
- **Kendini test et:** Giriş yaptıktan sonra token nerede saklanıyor ve her istekte nasıl gönderiliyor?

### 🟡 Tailwind CSS
- **Ne işe yarar:** Hazır küçük CSS sınıflarıyla hızlı tasarım.
- **Projede nerede:** [tailwind.config.js](../frontend/tailwind.config.js), `src/input.css` → `css/betula.css`
- **Araştır:** Utility-first CSS, build adımı (`npm run build:css`), CDN ile build arasındaki fark.

---

## Katman 6 — Kalite, dağıtım, araştırma

### 🟢 Test: pytest
- **Ne işe yarar:** Kodun doğru çalıştığını otomatik olarak kanıtlar. Değişiklik yapınca neyin bozulduğunu anında gösterir.
- **Projede nerede:** [tests/](../tests/), [conftest.py](../tests/conftest.py)
- **Araştır:**
  - Unit test ile entegrasyon testi farkı
  - **Fixture**
  - Mock / fake (testte sahte embedding kullandık; neden?)
  - `TestClient`
  - Test izolasyonu (geçici veritabanı)
- **Kendini test et:** Testler neden gerçek Groq'a istek atmıyor? Atsaydı ne sorun olurdu?

### 🟡 CI: GitHub Actions
- **Ne işe yarar:** Her push'ta testleri GitHub'ın sunucusunda otomatik çalıştırır; bozuk kod fark edilmeden ana dala girmez.
- **Projede nerede:** [.github/workflows/tests.yml](../.github/workflows/tests.yml)
- **Araştır:** Workflow, job, step, `on: push`; bağımlılık önbelleği; CI ve CD farkı.
- **Kendini test et:** CI'da torch'u neden ayrı bir adımda ve CPU sürümüyle kuruyoruz?

### 🟡 Gözlemlenebilirlik (telemetri ve loglama)
- **Ne işe yarar:** Hangi adımın ne kadar sürdüğünü ve kaç token harcadığını görmek. Hem maliyet takibi hem de makaledeki "gecikme/maliyet" tablosu için.
- **Projede nerede:** [telemetry.py](../backend/llm/telemetry.py) ve `model_calls` tablosu (`purpose` kolonu: `gap_analysis`, `synthesis`, `chat_rag`…)
- **Araştır:** Python `logging` modülü, `contextvars` (`track_llm_usage` bununla çalışıyor), metrik / log / trace ayrımı, LangSmith ve OpenTelemetry.
- **Kendini test et:** Bir Master Sentez işinin toplam token maliyetini SQL ile nasıl bulursun? (İpucu: `job_id`)

### 🟡 Docker
- **Ne işe yarar:** Uygulamayı "her bilgisayarda aynı çalışan" bir kutuya koyar.
- **Projede nerede:** [Dockerfile](../Dockerfile), [docker-compose.yml](../docker-compose.yml), [DEPLOY.md](../DEPLOY.md)
- **Araştır:** Image ile container farkı, katmanlar (layer), volume (veri neden `/data`'da tutuluyor?), ortam değişkenleri.
- **Kendini test et:** `docker compose down -v` neden tehlikeli?

### 🔵 Değerlendirme metrikleri (makale için kritik)
- **Ne işe yarar:** "Sistem iyi çalışıyor" iddiasını sayıyla kanıtlamak.
- **Projede nerede:** [evaluation/](../evaluation/), [metrics.py](../evaluation/metrics.py)
- **Araştır:**
  - **Precision, Recall, F1**; makro ve mikro ortalama farkı
  - Hit@k, MRR (bilgi getirme metrikleri)
  - Ground truth
  - Sentetik veri seti oluşturma
  - Baseline ve ablasyon çalışması
  - RAGAS (faithfulness, answer relevancy)
  - "LLM-as-a-judge"
- **Kendini test et:**
  - Duman testinde recall 1.0, precision 0.4 çıktı. Bu ne anlama geliyor ve nasıl düzeltilebilir?

### 🔵 Akademik yazım ve araştırma yöntemi
- **Araştır:**
  - Bir makalenin yapısı (Özet, Giriş, İlgili Çalışmalar, Yöntem, Deneyler, Sonuç)
  - "Katkı" (contribution) nasıl yazılır
  - Tekrarlanabilirlik
  - İlgili çalışmalar: RAG (Lewis ve ark., 2020), Self-RAG, Corrective RAG, eğitimde LLM kullanımı
  - Kullanıcı çalışması ve etik kurul
  - Literatür tarama araçları: Google Scholar, Semantic Scholar, Connected Papers
- **Kendini test et:** Betula'nın literatüre katkısını iki cümleyle yazabiliyor musun?

### 🔵 Aralıklı tekrar (Spaced Repetition): FSRS, SM-2
- **Ne işe yarar:** Faz 4'te "unutmayan" öğrenci modelinin temeli olacak. Henüz projede yok.
- **Araştır:** Ebbinghaus unutma eğrisi, SM-2 algoritması (Anki), FSRS, knowledge tracing.

---

## İlerleme takibi

| Konu | Kavram | Projede buldum | Deney yaptım | Kendime anlattım |
|---|---|---|---|---|
| Python ileri |  |  |  |  |
| Git |  |  |  |  |
| HTTP / REST |  |  |  |  |
| FastAPI |  |  |  |  |
| Pydantic |  |  |  |  |
| SQLite / SQL |  |  |  |  |
| Katmanlı mimari |  |  |  |  |
| JWT / OAuth |  |  |  |  |
| SSE |  |  |  |  |
| LLM temelleri |  |  |  |  |
| Groq |  |  |  |  |
| LangChain |  |  |  |  |
| RAG |  |  |  |  |
| Embedding |  |  |  |  |
| FAISS |  |  |  |  |
| LangGraph |  |  |  |  |
| PyMuPDF |  |  |  |  |
| JavaScript / DOM |  |  |  |  |
| pytest |  |  |  |  |
| GitHub Actions (CI) |  |  |  |  |
| Telemetri / loglama |  |  |  |  |
| Docker |  |  |  |  |
| Değerlendirme metrikleri |  |  |  |  |
| Akademik yazım |  |  |  |  |

> Bu dosya yaşayan bir belge: projeye yeni bir teknoloji eklendikçe buraya da eklenecek.
