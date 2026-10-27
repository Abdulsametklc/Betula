# Betula değerlendirme altyapısı

Makaledeki iddiaları ölçmek için kullanılan veri seti, metrikler ve deney betikleri.
Tüm betikler proje kökünden `python -m evaluation.<betik>` olarak çalıştırılır.

## 1. Korpus

```
evaluation/data/
├── corpus/<doc_id>/       # yeniden dağıtılabilir kaynaklar (git'te)
│   ├── meta.json          # title, filename, course, language, license, notes
│   └── source.pdf | source.docx | source.md | source.txt
├── private/<doc_id>/      # telifli ders notları — aynı yapı, git'e GİRMEZ
├── qa/<doc_id>.jsonl      # bilgi getirme soruları
└── generated/             # build_dataset çıktısı — git'e girmez, yeniden üretilir
```

- PDF ve DOCX dosyaları uygulamanın kendi okuyucusuyla (`backend/services/documents.py`) okunur, sayfa numaraları korunur.
- `.md` ve `.txt` kaynaklarında sayfa sınırları `<!-- page: N -->` satırıyla işaretlenir.
- **Kaynak seçimi:** Notlar *eksiksiz* ve başlıklı olmalıdır (`# Başlık`, `2.1 Başlık` ya da `BÜYÜK HARF`).
  Zaten eksik olan bir kaynakla çalışılırsa modelin bulduğu gerçek eksikler yanlış pozitif sayılır.
- `ornek-fizik-hareket` altyapıyı denemek için yazılmış kısa bir örnektir; deney sonucu olarak raporlanmaz.

## 2. Sentetik eksik ekleme (`gap_injection.py`)

Eksiksiz bir nottan rastgele `k` bölüm silinir; silinen bölümler, doğru cevabı bilinen eksiklerdir.

| Mod | Ne silinir | Senaryo |
|---|---|---|
| `body` (varsayılan) | Yalnızca gövde; başlık kalır | Konunun adı geçiyor ama anlatılmıyor |
| `full` | Başlık ve gövde | Konu tamamen kayıp (daha zor) |

Aynı `(doküman, mod, k, seed)` her zaman aynı örneği üretir.

```bash
python -m evaluation.build_dataset --k 3 --seeds 1 2 3 --mode body
```

## 3. Deneyler

**Eksik tespiti:** precision, recall ve F1 değerleri makro ve mikro ortalama olarak hesaplanır.

```bash
python -m evaluation.run_gap_eval                                  # pipeline (Groq)
python -m evaluation.run_gap_eval --predictions baseline.json --label baseline
```

Tahmin edilen konu ile gerçek başlık; Türkçe karakterleri sadeleştiren normalizasyonla birlikte
token örtüşmesi ve karakter benzerliğinin büyük olanına göre eşleştirilir (`--threshold`, varsayılan 0.6).
Eşleştirme bire birdir: aynı eksik iki kez doğru sayılmaz. Hazır tahmin dosyasının biçimi
`{"<sample_id>": ["konu", ...]}` şeklindedir; başka sistemler (NotebookLM, düz LLM özeti vb.) bu
yolla karşılaştırılır.

**Bilgi getirme:** doğru kanıt sayfasının getirilen ilk `k` parçada bulunup bulunmadığı ölçülür
(Hit@1, Hit@3, Hit@5 ve MRR).

```bash
python -m evaluation.run_retrieval_eval --k 5
python -m evaluation.run_retrieval_eval --fake-embeddings          # ağsız duman testi
```

Uygulamayla aynı parçalama (`chunk_pages`) kullanılır. Böylece parça boyutu, embedding modeli
veya yeniden sıralama değişikliklerinin etkisi doğrudan ölçülür.

## 4. Sonuçlar ve tekrarlanabilirlik

Her çalıştırma, `evaluation/results/<tür>_<zaman>.json` dosyasına şu bilgilerle kaydedilir:

- git commit (kaydedilmemiş değişiklik varsa `-dirty` eki),
- model adı ve prompt özeti (`gap_prompt_sha`),
- eşik ve parça ayarları,
- örnek başına tahminler ve süreler.

Makalede kullanılan sonuç dosyaları bilinçli olarak commit edilmelidir.

## 5. Sıradaki adımlar

- [ ] 30–50 adet eksiksiz Türkçe ders notu (farklı dersler); lisans durumu `meta.json`'da belirtilmeli
- [ ] Her doküman için 10 veya daha fazla soru-kanıt sayfası çifti (`qa/`)
- [ ] Baseline sistemler: düz LLM özeti, klasik RAG, NotebookLM (elle)
- [ ] Ablasyon bayrakları: web araştırması / doğrulama / hafıza kapalı
- [ ] Eşik duyarlılığı: 0.5 / 0.6 / 0.7 için sonuçların raporlanması
