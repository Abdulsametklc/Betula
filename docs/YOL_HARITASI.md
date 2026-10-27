# Betula — Yol Haritası ve Makale Planı

**Hedef:** Hızlı, verimli, akıllı ve unutmayan; piyasadaki muadilleriyle yarışabilecek, dar bir alanda
(Türkçe ders materyali → eksiksiz çalışma notu → pekiştirme) çok güçlü bir "PDF canavarı".

**Öncelik sırası:**
1. Projeyi makale olarak yayımlamak.
2. Ürünü sunulabilir ve öne çıkarılabilir bir derinliğe taşımak; yapıları sağlam kurmak.

Her faz hem ürünü güçlendirir hem de makaleye ölçülebilir veri üretir.

---

## Konumlanma

| | NotebookLM / ChatPDF / Humata | Quizlet AI / Knowt | **Betula** |
|---|---|---|---|
| Belgede olanı anlatır | ✅ | kısmen | ✅ (sayfa ve bölüm kaynaklı) |
| **Belgede olmayanı bulur** | ❌ | ❌ | ✅ eksik tespiti |
| **Eksiği kaynaklı biçimde tamamlar** | ❌ | ❌ | ✅ web araştırması ve sentez |
| Quiz ve flashcard | kısmen | ✅ | ✅ |
| **Öğrencinin zayıf noktalarını unutmaz** | ❌ | kısmen | 🔜 Faz 4 |
| Türkçe öncelikli | ❌ | ❌ | ✅ |

---

## Makale çerçevesi

**Çalışma başlığı:** *Eksiği fark eden RAG: Türkçe ders materyallerinde ajan tabanlı eksik bilgi tespiti,
kaynaklı tamamlama ve öğrenciye uyarlanan pekiştirme*

**Katkılar:**
1. Eksik tespiti, web'de doğrulamalı tamamlama ve kaynaklı sentez yapan bir ajan mimarisi (LangGraph).
2. Türkçe ders notlarından oluşan, **sentetik eksik eklemeyle** doğru cevabı bilinen eksikler üretilen bir değerlendirme veri seti.
3. Öğrenci modeli tutan hafıza ile quiz ve aralıklı tekrar döngüsü.

**Deney tasarımı:**
- **Metrikler:**
  - eksik tespiti: P / R / F1 (makro ve mikro)
  - bilgi getirme: Hit@k, MRR
  - sadakat ve kaynak doğruluğu: RAGAS faithfulness, kaynak gösterme isabeti
  - gecikme ve token maliyeti
- **Baseline'lar:** sadece LLM özeti, klasik RAG, NotebookLM (elle).
- **Ablasyonlar:** eksik analizi / web araştırması / doğrulama / hafıza kapalı.
- **Kullanıcı çalışması (ideal):** 20–40 öğrenciyle ön test / son test ve SUS anketi; etik kurul izni gerekebilir.
- **Yayın yeri adayları:** UBMK, SIU, ASYU, DergiPark dergileri; sonuçlar güçlü çıkarsa uluslararası eğitim teknolojisi ve NLP workshop'ları.

Ayrıntılı protokol: [evaluation/README.md](../evaluation/README.md)

---

## Faz 0 — Temel ✅ (tamamlandı, 2026-10-27)

- [x] Sayfa bilgili belge okuma (PDF sayfa no, DOCX tek mantıksal sayfa); `documents.pages_json`
- [x] Bölüm (başlık) tespiti: büyük puntolu PDF satırları ve numaralı, markdown, BÜYÜK HARF başlıklar
- [x] Kaynağı koruyan parçalama: dosya, sayfa, bölüm, sıra, karakter konumu; parçalar sayfa ve bölüm sınırını aşmaz
- [x] Cevaplarda kaynak gösterme: `[ders.pdf · s. 12 · İvme]`
- [x] Belge bazında indeks yenileme (ikinci belgenin ilkini silmesi hatası giderildi)
- [x] Eski indeksleri yenileme betiği: `scripts/reindex_vectorstores.py`
- [x] LLM çağrı telemetrisi: her çağrı amaç, model, token, süre ve hata ile `model_calls` tablosuna yazılıyor
- [x] Groq modelleri güncellendi: Llama 3.x kaldırılmıştı → `gpt-oss-120b` / `gpt-oss-20b` (ayarlardan değiştirilebilir)
- [x] pytest altyapısı (ağ ve Groq gerektirmez) ve GitHub Actions CI
- [x] Değerlendirme iskeleti: korpus, sentetik eksik ekleme, metrikler, deney betikleri, örnek doküman

**Faz 0 duman testi bulguları** (örnek çok küçük; yalnızca yön gösterir):
- **Eksik tespiti (gpt-oss-120b):** recall 1.00, **precision 0.40**. Model prompt'taki "en fazla 5" ifadesini "tam 5" gibi yorumlayıp gerçekte eksik olmayan konuları da eksik sayıyor. → Faz 3'te kalibrasyon.
- **Bilgi getirme (MiniLM):** Hit@1 0.50, Hit@5 1.00. Doğru sayfa bulunuyor ama ilk sırada değil. → Faz 2'de reranker ve daha güçlü embedding.

## Faz 1 — Okuma ve uzun belge

- [ ] Sentez ve eksik analizinde 35–40 bin karakter sınırını kaldırmak: **bölüm bölüm map-reduce** (her bölüm ayrı analiz edilip birleştirilir)
- [ ] Taranmış PDF için OCR (Tesseract / PaddleOCR); metni olmayan sayfaların tespiti
- [ ] Tablo ve formül çıkarımı (`pymupdf4llm`, Markdown tablo)
- [ ] Aynı belgenin tekrar yüklenmesini checksum ile tanıma
- [ ] Ölçüm: uzun belgelerde (50–300 sayfa) eksik tespiti recall değerinin kesmeli sürümle karşılaştırılması

## Faz 2 — Bilgi getirme

- [ ] Hibrit arama: BM25 + vektör
- [ ] Çok dilli reranker (`bge-reranker-v2-m3`)
- [ ] Embedding karşılaştırması: MiniLM, `bge-m3`, `multilingual-e5` (`run_retrieval_eval` ile)
- [ ] Arayüzde tıklanabilir kaynak: pdf.js ile ilgili sayfanın açılıp metnin vurgulanması
- [ ] Ölçüm: Hit@1 ve MRR değerlerinde her bileşenin katkısı (ablasyon)

## Faz 3 — Akıllı ajan

- [ ] Eksik kalibrasyonu: yalnızca gerçek eksikleri döndürme, güven puanı, "eksik yok" cevabına izin verme (precision hedefi ≥ 0.7)
- [ ] "Doğrula → yetersizse yeniden ara" döngüsü (LangGraph conditional edge)
- [ ] Kaynak güven puanı: alan adı beyaz listesi, akademik ve resmi kaynak önceliği
- [ ] Human-in-the-loop: kullanıcı eksik listesini onaylar veya düzenler
- [ ] Sentez iddialarının kaynakla eşleştirilmesi (halüsinasyon kontrolü, RAGAS faithfulness)

## Faz 4 — Unutmayan öğrenci modeli

- [ ] Konu grafiği: belgeler ve oturumlar arası kavram bağlantıları
- [ ] Quiz sonuçlarından konu başına bilgi düzeyi tahmini (knowledge tracing)
- [ ] Flashcard'lar için FSRS veya SM-2 aralıklı tekrar zamanlaması
- [ ] Oturumlar arası hatırlatma: "Bu kavramı geçen hafta Fizik oturumunda zorlanmıştın"
- [ ] Ölçüm: kullanıcı çalışmasında ön test / son test farkı

## Faz 5 — Hız ve sağlamlık

- [ ] Hash tabanlı LLM önbelleği (aynı belge ve prompt için tekrar çağrı yapılmaması)
- [ ] Pipeline ilerlemesinin polling yerine SSE ile canlı gelmesi
- [ ] İş kuyruğu (RQ / arq) ve yeniden deneme
- [ ] Gerçek migration sistemi; `modules/` ile `backend/` katmanlarının tek yapıda birleştirilmesi
- [ ] Ölçeklemede PostgreSQL ve pgvector değerlendirmesi
- [ ] Git geçmişindeki eski `LocalInsights.db` dosyasının temizlenmesi (gerçek kullanıcı verisi varsa)

---

## Açık riskler

- **Groq model ömrü:** Modeller haber verilmeden kaldırılabiliyor (Llama 3.x örneği). Deneylerde kullanılan model sürümü sonuç dosyalarına yazılıyor; makale yazılırken sabitlenmeli.
- **Telif:** Değerlendirme korpusundaki ders notlarının lisansı `meta.json` dosyasında tutulmalı; telifli materyal `evaluation/data/private/` altında kalmalı.
- **Prompt'lar Llama'ya göre yazılmıştı:** GPT-OSS ile çıktı biçimi ve kalitesi yeniden gözden geçirilmeli. Faz 3'teki kalibrasyon bu işle birlikte yapılabilir.
