"""LocalInsights FastAPI entrypoint."""

from __future__ import annotations

import os
import sys

# Ensure project root is on sys.path when running: uvicorn backend.main:app
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.routers import auth, chat, documents, memory, pipeline, sessions, study
from backend.config import get_settings
from modules.db import init_db

FRONTEND_DIR = Path(ROOT) / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    os.makedirs(settings.vectorstore_root, exist_ok=True)
    os.makedirs(settings.uploads_root, exist_ok=True)
    init_db()
    yield


app = FastAPI(
    title="Betula API",
    description="Groq + LangGraph research study assistant",
    version="2.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(sessions.router)
app.include_router(documents.router)
app.include_router(pipeline.router)
app.include_router(chat.router)
app.include_router(memory.router)
app.include_router(study.router)

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
def home():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "LocalInsights API", "docs": "/docs"}


@app.get("/sessions-page")
@app.get("/oturumlar")
def sessions_page():
    page = FRONTEND_DIR / "sessions.html"
    if page.exists():
        return FileResponse(page)
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/app")
def workspace():
    page = FRONTEND_DIR / "app.html"
    if page.exists():
        return FileResponse(page)
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "provider": "groq", "model": settings.groq_model}


@app.get("/models")
def models():
    from backend.llm import FAST_MODEL, QUALITY_MODEL, default_model_name

    return {
        "default": default_model_name(),
        "provider": "groq",
        "models": [
            {"id": QUALITY_MODEL, "label": "Llama 3.3 70B (kalite)"},
            {"id": FAST_MODEL, "label": "Llama 3.1 8B (hizli)"},
        ],
    }
