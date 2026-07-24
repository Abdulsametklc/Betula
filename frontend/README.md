# Betula Frontend

Stitch tasarımları API’ye bağlandı.

## Sayfalar

| URL | Dosya | Açıklama |
|-----|--------|----------|
| `/` | `index.html` | Ana sayfa + giriş/kayıt |
| `/app` | `app.html` | Çalışma alanı |
| `/static/js/*` | `js/` | API client + workspace logic |

## Çalıştırma

```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Tarayıcı: http://127.0.0.1:8000

## Akış

1. Ana sayfada **Başla / Keşfet** → giriş veya kayıt
2. `/app` çalışma alanı
3. PDF/DOCX yükle → pipeline poll → Master Sentez
4. Chat, flashcard, quiz
