"""Groq chat model factory — fixed defaults, no model picking required."""

from __future__ import annotations

from functools import lru_cache

from langchain_groq import ChatGroq

from backend.config import get_settings
from backend.llm.telemetry import LLMCallLogger

# Varsayilan model secimi (.env'deki GROQ_MODEL / GROQ_FAST_MODEL ile degistirilebilir)
QUALITY_MODEL = "openai/gpt-oss-120b"  # chat, gap, synthesis, study
FAST_MODEL = "openai/gpt-oss-20b"  # memory extract, web research summaries, titles

MODEL_LABELS = {
    QUALITY_MODEL: "GPT-OSS 120B (kalite)",
    FAST_MODEL: "GPT-OSS 20B (hizli)",
}


def get_chat_model(
    temperature: float = 0.2,
    model_name: str | None = None,
    *,
    fast: bool = False,
    purpose: str | None = None,
    user_id: int | None = None,
    session_id: int | None = None,
    job_id: int | None = None,
    conversation_id: int | None = None,
) -> ChatGroq:
    """Groq istemcisi; her cagri ``purpose`` etiketiyle token ve sure olarak loglanir."""
    settings = get_settings()
    if not settings.groq_api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Copy .env.example to .env and add your Groq key "
            "(https://console.groq.com/keys)."
        )
    chosen = model_name or (settings.groq_fast_model if fast else settings.groq_model)
    logger = LLMCallLogger(
        model_name=chosen,
        purpose=purpose,
        user_id=user_id,
        session_id=session_id,
        job_id=job_id,
        conversation_id=conversation_id,
    )
    return ChatGroq(
        model=chosen,
        api_key=settings.groq_api_key,
        temperature=temperature,
        callbacks=[logger],
    )


@lru_cache
def default_model_name() -> str:
    return get_settings().groq_model


def available_models() -> list[dict]:
    """/models uclari icin: ayarlardaki kalite ve hizli model."""
    settings = get_settings()
    return [
        {"id": settings.groq_model, "label": MODEL_LABELS.get(settings.groq_model, f"{settings.groq_model} (kalite)")},
        {"id": settings.groq_fast_model, "label": MODEL_LABELS.get(settings.groq_fast_model, f"{settings.groq_fast_model} (hizli)")},
    ]
