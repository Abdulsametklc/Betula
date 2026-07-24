"""Groq chat model factory — fixed defaults, no model picking required."""

from __future__ import annotations

from functools import lru_cache

from langchain_groq import ChatGroq

from backend.config import get_settings

# Fixed model choices (user only needs GROQ_API_KEY)
QUALITY_MODEL = "llama-3.3-70b-versatile"  # chat, gap, synthesis, study
FAST_MODEL = "llama-3.1-8b-instant"  # memory extract, web research summaries


def get_chat_model(
    temperature: float = 0.2,
    model_name: str | None = None,
    *,
    fast: bool = False,
) -> ChatGroq:
    settings = get_settings()
    if not settings.groq_api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Copy .env.example to .env and add your Groq key "
            "(https://console.groq.com/keys)."
        )
    chosen = model_name or (FAST_MODEL if fast else settings.groq_model)
    return ChatGroq(
        model=chosen,
        api_key=settings.groq_api_key,
        temperature=temperature,
    )


@lru_cache
def default_model_name() -> str:
    return get_settings().groq_model
