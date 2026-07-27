"""Sohbet basligi uretimi — icerige gore kisa Turkce baslik."""

from __future__ import annotations

import re

from backend.llm import get_chat_model

_TITLE_PROMPT = """Asagidaki egitim sohbeti icin kisa bir Turkce baslik yaz.
Kurallar:
- En fazla 6 kelime
- Sadece basligi yaz, tirnak veya aciklama ekleme
- Konuyu ozetle (ornek: "Redi formulu aciklamasi", "Sinir agi ogrenme orani")

Kullanici: {question}

Asistan (ozet): {answer}
"""


def generate_conversation_title(question: str, answer: str = "") -> str:
    q = (question or "").strip()
    a = (answer or "").strip()
    if not q:
        return "Yeni Sohbet"
    try:
        llm = get_chat_model(temperature=0.2, fast=True)
        raw = llm.invoke(
            _TITLE_PROMPT.format(question=q[:500], answer=(a[:700] or "(henuz yok)"))
        )
        text = raw.content if hasattr(raw, "content") else str(raw)
        title = (text or "").strip().splitlines()[0].strip().strip("\"'`")
        title = re.sub(r"^baslik\s*[:：]\s*", "", title, flags=re.I)
        title = re.sub(r"\s+", " ", title).strip()
        if 2 <= len(title) <= 80:
            return title[:72]
    except Exception as e:
        print(f"title gen error: {e}")
    # Fallback: ilk cumle / kelimeler
    clean = re.sub(r"\s+", " ", q)
    if len(clean) <= 48:
        return clean
    return clean[:45].rstrip() + "…"
