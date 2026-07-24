"""
RAG Engine Module
Retrieval-Augmented Generation + personalization (Groq).
"""

from __future__ import annotations

from typing import Generator, Iterable

from langchain_core.prompts import ChatPromptTemplate

from backend.llm import get_chat_model
from backend.services.vectorstore import (
    add_to_vector_db as _add,
    create_vector_db as _create,
    load_vector_db as _load,
)


def create_vector_db(text, persist=False, user_id: int | None = None):
    if user_id is None:
        raise ValueError("create_vector_db requires user_id")
    return _create(text, user_id=user_id, persist=persist)


def load_vector_db(user_id: int | None = None):
    if user_id is None:
        raise ValueError("load_vector_db requires user_id")
    return _load(user_id=user_id)


def add_to_vector_db(text, existing_vectorstore=None, user_id: int | None = None):
    if user_id is None:
        raise ValueError("add_to_vector_db requires user_id")
    return _add(text, user_id=user_id, existing=existing_vectorstore)


def get_personalized_context(user_id: int = None):
    if not user_id:
        return "Kullanıcı hakkında özel bilgi yok.", ""

    try:
        from .memory_engine import build_memory_context

        memory_context = build_memory_context(user_id)
        if memory_context:
            return memory_context, ""
        return "Kullanıcı hakkında özel bilgi yok.", ""
    except Exception as e:
        print(f"Memory context error: {e}")
        return "Kullanıcı hakkında özel bilgi yok.", ""


_RAG_TEMPLATE = """Sen Betula asistanısın - akıllı, yardımsever ve kişiselleştirilmiş bir eğitim asistanısın.

⚠️ DİL KURALI: SADECE TÜRKÇE YANIT VER. ASLA BAŞKA DİL KULLANMA.

KULLANICI BİLGİLERİ:
{user_profile}

{learning_context}

DÖKÜMAN İÇERİĞİ:
{pdf_context}

{history_section}

KULLANICI SORUSU: {question}

KRİTİK KURALLAR:
- SADECE TÜRKÇE YANIT VER.
- SADECE DÖKÜMAN İÇERİĞİNDEKİ bilgileri kullan. Uydurma yapma.
- Bilgi dokümanda yoksa açıkça belirt.
- Yapılandırılmış ve anlaşılır yanıtlar ver.

🇹🇷 TÜRKÇE YANITINI VER:"""

_QUICK_TEMPLATE = """Sen Betula asistanısın - akıllı ve yardımsever bir eğitim asistanı.

⚠️ DİL KURALI: SADECE TÜRKÇE YANIT VER.

KULLANICI BİLGİLERİ: {user_profile}

KULLANICI SORUSU: {question}

KRİTİK KURALLAR:
- SADECE TÜRKÇE YANIT VER.
- Kısa ve samimi ol.
- Uydurma yapma, bilmiyorsan söyle.

🇹🇷 TÜRKÇE YANITINI VER:"""


def _history_section(chat_history) -> str:
    if not chat_history:
        return ""
    history_text = ""
    for msg in chat_history[-6:]:
        role = "Kullanıcı" if msg["role"] == "user" else "Asistan"
        history_text += f"{role}: {msg['content'][:200]}\n"
    return f"SON SOHBET GEÇMİŞİ:\n{history_text}"


def _chunk_text(chunk) -> str:
    if chunk is None:
        return ""
    if hasattr(chunk, "content"):
        content = chunk.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            return "".join(parts)
        return str(content) if content else ""
    return str(chunk)


def _stream_chain(chain, inputs: dict) -> Generator[str, None, None]:
    for chunk in chain.stream(inputs):
        text = _chunk_text(chunk)
        if text:
            yield text


def get_ai_response(model_name, vectorstore, user_question, chat_history=None, user_id=None):
    try:
        user_profile, learning_context = get_personalized_context(user_id=user_id)
        docs = vectorstore.similarity_search(user_question, k=4)
        pdf_context = "\n\n".join([doc.page_content for doc in docs])
        prompt = ChatPromptTemplate.from_template(_RAG_TEMPLATE)
        llm = get_chat_model(temperature=0.1, model_name=model_name if model_name else None)
        chain = prompt | llm
        response = chain.invoke(
            {
                "user_profile": user_profile,
                "learning_context": learning_context,
                "pdf_context": pdf_context,
                "history_section": _history_section(chat_history),
                "question": user_question,
            }
        )
        return response.content, docs
    except Exception as e:
        return f"HATA: {e}", []


def stream_ai_response(
    model_name, vectorstore, user_question, chat_history=None, user_id=None
) -> tuple[Iterable[str], list]:
    user_profile, learning_context = get_personalized_context(user_id=user_id)
    docs = vectorstore.similarity_search(user_question, k=4)
    pdf_context = "\n\n".join([doc.page_content for doc in docs])
    prompt = ChatPromptTemplate.from_template(_RAG_TEMPLATE)
    llm = get_chat_model(temperature=0.1, model_name=model_name if model_name else None)
    chain = prompt | llm
    inputs = {
        "user_profile": user_profile,
        "learning_context": learning_context,
        "pdf_context": pdf_context,
        "history_section": _history_section(chat_history),
        "question": user_question,
    }
    return _stream_chain(chain, inputs), docs


def get_quick_answer(model_name, question, user_id=None):
    try:
        user_profile, _ = get_personalized_context(user_id=user_id)
        prompt = ChatPromptTemplate.from_template(_QUICK_TEMPLATE)
        llm = get_chat_model(temperature=0.2, model_name=model_name if model_name else None)
        chain = prompt | llm
        response = chain.invoke({"user_profile": user_profile, "question": question})
        return response.content
    except Exception as e:
        return f"HATA: {e}"


def stream_quick_answer(model_name, question, user_id=None) -> Iterable[str]:
    user_profile, _ = get_personalized_context(user_id=user_id)
    prompt = ChatPromptTemplate.from_template(_QUICK_TEMPLATE)
    llm = get_chat_model(temperature=0.2, model_name=model_name if model_name else None)
    chain = prompt | llm
    return _stream_chain(chain, {"user_profile": user_profile, "question": question})
