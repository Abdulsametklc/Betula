<p align="center">
  <img src="frontend/assets/betula-mark.svg" alt="Betula" width="112" height="112"/>
</p>

<h1 align="center">Betula</h1>

**Bilgelik ağacı.** Notlarınızı okur, eksiklerini bulur, araştırır ve sizin için bütün bir çalışma notuna dönüştürür.

Betula; ders notları, PDF’ler ve belgelerle çalışırken “ne eksik?” sorusunu sizin yerinize soran bir çalışma asistanıdır. Kaynağı yüklediğinizde boşlukları tespit eder, güvenilir web sonuçlarıyla tamamlar ve Master Sentez olarak sunar. Aynı oturumda sohbet eder, quiz çözer, flashcard üretir; her şey tek bir çalışma alanında kalır.

---

## Ne işe yarar?

- **Dağınık notları birleştirir** — Yarım kalmış, dağınık veya eksik anlatımlı materyalleri okunabilir, hiyerarşik bir senteze çevirir.
- **Eksikleri görünür kılar** — Anlaşılmayan veya atlanan konuları tespit eder; her birini ekranda özet ve kaynaklarıyla gösterir.
- **Aktif öğrenmeyi destekler** — Konuya özel çoktan seçmeli ve doğru/yanlış quiz’ler, flashcard’lar ve sohbetle pekiştirme.
- **Çalışmayı ayırır** — Her oturum kendi kaynakları, sohbetleri, quiz arşivi ve sentezleriyle bağımsız bir çalışma alanıdır.

Kısaca: Betula, “yükle → anla → tamamla → pekiştir” döngüsünü tek ürün olarak sunar.

---

## Özellikler

**Çalışma oturumları**  
Her ders veya proje için ayrı bir alan. İsim verin; kaynaklar, sohbet geçmişi, quiz arşivi ve eksik bilgiler o oturumda kalsın.

**Master Sentez**  
Yüklenen belge taranır, eksikler bulunur, web araştırması yapılır ve Markdown çalışma notu üretilir. Süreç boyunca anlaşılır durum mesajları ve kısa “biliyor muydun?” ipuçları eşlik eder.

**Eksik bilgilerin keşfi**  
Tespit edilen boşluklar konuya göre listelenir; araştırma özetleri ve kaynak bağlantıları doğrudan panoda okunur.

**Akıllı sohbet**  
Belge ve sentez bağlamına dayalı yanıtlar. Cevaplar akışkan (streaming) gelir; yazılırken okursunuz.

**Quiz ve flashcard**  
Çoktan seçmeli ve doğru/yanlış sorular. Soru sayısı (5 / 10 / 15) ve konu seçimi. Tamamlanan denemeler arşivlenir; yarım kalanlar yeniden sorulabilir.

**Kişisel hafıza**  
Tercihlerinizi ve öğrenme bağlamınızı hatırlar; sohbeti size göre şekillendirir.

---

## Teknolojiler

| Katman | Seçim |
|--------|--------|
| API | FastAPI |
| Dil modeli | Groq (Llama ailesi) |
| Ajan / boru hattı | LangGraph |
| Erişim artırımlı üretim | LangChain + FAISS |
| Belge okuma | PyMuPDF, python-docx |
| Web araştırma | DuckDuckGo |
| Veri | SQLite |
| Arayüz | Modern HTML / CSS / JS (Betula teması) |
| Kimlik | JWT |

Hızlı çıkarım için Groq; yapılandırılmış araştırma için LangGraph; belgeye bağlı cevaplar için RAG. Hepsi tek bir monolit hizmette bir araya gelir — kurması ve anlaması sade, etkisi derin.

---

## Neden “Betula”?

*Betula*, huş ağacının Latince adıdır. Yazıya, hafızaya ve yenilenmeye işaret eder. Ürün de aynı ruhla tasarlandı: kökleri sizin kaynaklarınızda, dalları araştırmada, yaprakları ise sentezlenmiş bilgide.

---

*Bilgiyi yükle. Eksikleri tamamla. Öğrenmeyi büyüt.*
