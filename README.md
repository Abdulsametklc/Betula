# Betula

Yerel-first çalışma asistanından bulut tabanlı (Groq) araştırma boru hattına geçiş.

## Özellikler

- JWT auth (kayıt / giriş)
- PDF/DOCX yükleme (PyMuPDF)
- LangGraph pipeline: Parse → Gap analizi → DuckDuckGo araştırma → Markdown sentez
- Kullanıcı bazlı kalıcı FAISS
- RAG sohbet + hafıza motoru
- Flashcard / quiz API

## Kurulum

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

`.env` içine [Groq Console](https://console.groq.com/keys) anahtarını yaz:

```
GROQ_API_KEY=gsk_...
```

Model seçmen gerekmez. Varsayılanlar:
- Kalite: `llama-3.3-70b-versatile` (chat, sentez, quiz)
- Hızlı: `llama-3.1-8b-instant` (hafıza, web özetleri)

## Çalıştırma

Proje kökünden:

```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

- API docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

## Frontend (Stitch)

- Ana sayfa: http://127.0.0.1:8000/
- Çalışma alanı: http://127.0.0.1:8000/app
- Kaynak: `frontend/`

## Notlar

- Web arama varsayılanı DuckDuckGo (ücretsiz).
- Streamlit / Ollama / Gemini kaldırıldı.
