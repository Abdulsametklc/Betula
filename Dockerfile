FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY backend ./backend
COPY modules ./modules
COPY frontend ./frontend

RUN mkdir -p /data/uploads /data/vectorstore \
    && chmod -R 755 /data

ENV DATABASE_PATH=/data/LocalInsights.db \
    UPLOADS_ROOT=/data/uploads \
    VECTORSTORE_ROOT=/data/vectorstore \
    DEBUG=false

EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
