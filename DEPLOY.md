# Deploy & operasyon — Betula

Betula yerel masaüstü uygulaması değil; **FastAPI + statik frontend** monolit web uygulamasıdır.
Tek süreç (`uvicorn`) hem API’yi hem sayfaları (`/`, `/app`, `/hakkinda`, …) sunar.

## Web için uygunluk

| Uygun | Dikkat |
|-------|--------|
| Groq bulut LLM | SQLite + FAISS + yüklemeler diskte → **kalıcı volume** şart |
| JWT auth, HTTPS arkası | Tek instance; multi-replica için Postgres/vektör DB gerekir |
| Same-origin frontend | `JWT_SECRET`, `DEBUG=false`, gerçek `CORS_ORIGINS` |
| Aktivasyon maili (SMTP) | Embedding modeli ilk açılışta indirilir (RAM/CPU) |

Özet: **tek VPS veya tek container + volume** ile web olarak çalışır. Ephemeral PaaS (disk silinen free plan) veri kaybettirir.

## Ortam değişkenleri

`.env.example` dosyasını kopyalayın. Prod için kritikler:

- `GROQ_API_KEY`
- `JWT_SECRET` (uzun, rastgele)
- `DEBUG=false`
- `CORS_ORIGINS=https://senin-domainin.com`
- `DATABASE_PATH` / `UPLOADS_ROOT` / `VECTORSTORE_ROOT` → volume yolları
- SMTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`

## Docker ile çalıştırma

```bash
cp .env.example .env
# .env düzenle

docker compose build
docker compose up -d
```

- **Build:** `docker compose build` (kod veya requirements değişince)
- **Restart:** `docker compose restart` veya `docker compose up -d --force-recreate`
- **Log:** `docker compose logs -f betula`
- **Stop:** `docker compose down` (volume silinmez; silmek için `down -v`)

Uygulama: `http://localhost:8000` — health: `/health`

## VPS’te (Docker’suz)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# .env hazır
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Prod’da systemd veya process manager ile tutun; Nginx/Caddy ile HTTPS reverse proxy önerilir.

Örnek systemd `ExecStart`:

```
/path/to/.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Restart: `systemctl restart betula`

## Frontend CSS

`frontend/css/betula.css` repoda hazırdır. Tailwind sınıflarını değiştirirseniz:

```bash
cd frontend && npm install && npm run build:css
```

Sonra imajı yeniden build edin / dosyaları sunucuya kopyalayın.

## E-posta / şifre aktivasyonu

**Hesap (oturum açık):**
1. Kullanıcı Hesap’tan “değiştir” der → mevcut mailine 6 haneli kod gider
2. Kod ortadaki modalda girilir ve doğrulanır
3. Yeni e-posta veya şifre girilir → DB güncellenir

**Şifremi unuttum (giriş ekranı):**
1. E-posta **veya** kullanıcı adı girilir → hesaba bağlı maile kod + `/sifre-sifirla` bağlantısı gider
2. Kod doğrulanır → yeni şifre belirlenir

SMTP yokken `DEBUG=true` ise kod konsola yazılır ve API yanıtında `dev_code` döner (sadece geliştirme).

## OAuth (Google / GitHub)

1. Google Cloud Console → OAuth Client (Web) oluştur  
   Redirect: `http://127.0.0.1:8000/auth/oauth/google/callback`
2. GitHub → Settings → Developer settings → OAuth Apps  
   Callback: `http://127.0.0.1:8000/auth/oauth/github/callback`
3. `.env` içine `GOOGLE_CLIENT_ID/SECRET` ve `GITHUB_CLIENT_ID/SECRET` yaz  
4. `PUBLIC_BASE_URL=http://127.0.0.1:8000` (veya canlı URL)
5. Sunucuyu yeniden başlat — giriş modalında butonlar görünür

Client ID yoksa butonlar gizlenir; e-posta/şifre girişi çalışmaya devam eder.


1. `git pull`
2. `docker compose build`
3. `docker compose up -d`
4. `/health` kontrol

Veri `/data` volume’unda kalır; rebuild DB’yi silmez.
