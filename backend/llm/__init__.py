"""LLM package — Groq is the default provider."""

from backend.llm.groq import FAST_MODEL, QUALITY_MODEL, default_model_name, get_chat_model

__all__ = [
    "get_chat_model",
    "default_model_name",
    "QUALITY_MODEL",
    "FAST_MODEL",
]
