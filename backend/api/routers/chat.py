"""Chat and conversation routes."""

from __future__ import annotations

import json
import time
from typing import Generator, Iterable

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.auth.deps import CurrentSession, CurrentUser
from backend.llm import default_model_name
from backend.schemas import ChatRequest, ChatResponse, ConversationCreate
from backend.services.enrichment import (
    assess_coverage,
    persist_ek_bilgi,
    research_and_answer,
)
from backend.services.vectorstore import load_vector_db
from modules.memory_engine import format_memory_response, process_memory_extraction
from modules.rag_engine import (
    get_ai_response,
    get_quick_answer,
    stream_ai_response,
    stream_quick_answer,
)
from modules.repo_chat import (
    create_conversation,
    create_message,
    get_conversation,
    get_messages,
    list_conversations,
    log_model_call,
)
from modules.repo_documents import get_document
from modules.repo_pipeline import get_compiled_note_for_document
from modules.repo_sessions import touch_session

router = APIRouter(tags=["chat"])


@router.get("/conversations")
def conversations_list(user: CurrentUser, session: CurrentSession):
    return list_conversations(user_id=user["id"], session_id=session["id"])


@router.post("/conversations")
def conversations_create(body: ConversationCreate, user: CurrentUser, session: CurrentSession):
    existing = list_conversations(user_id=user["id"], session_id=session["id"], limit=1)
    if existing:
        return existing[0]
    cid = create_conversation(
        user_id=user["id"],
        title=body.title,
        model_name=default_model_name(),
        session_id=session["id"],
    )
    touch_session(session["id"], user_id=user["id"])
    return get_conversation(cid, user_id=user["id"])


@router.get("/conversations/{conversation_id}")
def conversations_get(conversation_id: int, user: CurrentUser, session: CurrentSession):
    conv = get_conversation(conversation_id, user_id=user["id"])
    if not conv or (conv.get("session_id") and conv.get("session_id") != session["id"]):
        raise HTTPException(status_code=404, detail="Sohbet bulunamadi")
    return conv


@router.delete("/conversations/{conversation_id}")
def conversations_delete(conversation_id: int, user: CurrentUser, session: CurrentSession):
    raise HTTPException(
        status_code=400,
        detail="Her oturumda tek sohbet vardir; sohbet silinemez",
    )


@router.get("/conversations/{conversation_id}/messages")
def conversations_messages(conversation_id: int, user: CurrentUser, session: CurrentSession):
    conv = get_conversation(conversation_id, user_id=user["id"])
    if not conv or (conv.get("session_id") and conv.get("session_id") != session["id"]):
        raise HTTPException(status_code=404, detail="Sohbet bulunamadi")
    return get_messages(conversation_id, user_id=user["id"])


def _prepare_chat(body: ChatRequest, user: dict, session: dict) -> dict:
    """Ortak sohbet hazirligi: conversation, memory, history."""
    user_id = user["id"]
    model = default_model_name()
    session_id = session["id"]

    conversation_id = body.conversation_id
    if conversation_id:
        conv = get_conversation(conversation_id, user_id=user_id)
        if not conv or (conv.get("session_id") and conv.get("session_id") != session_id):
            raise HTTPException(status_code=404, detail="Sohbet bulunamadi")
    else:
        existing = list_conversations(user_id=user_id, session_id=session_id, limit=1)
        if existing:
            conversation_id = existing[0]["id"]
        else:
            conversation_id = create_conversation(
                user_id=user_id,
                title="Sohbet",
                model_name=model,
                session_id=session_id,
            )

    create_message(conversation_id, "user", body.message, user_id=user_id)
    touch_session(session_id, user_id=user_id)

    memory_result = process_memory_extraction(model, body.message, user_id=user_id)
    memory_note = format_memory_response(memory_result.get("command_responses") or [])

    history = get_messages(conversation_id, user_id=user_id, limit=20)
    chat_history = [{"role": m["role"], "content": m["content"]} for m in history[:-1]]

    return {
        "user_id": user_id,
        "model": model,
        "conversation_id": conversation_id,
        "memory_note": memory_note,
        "chat_history": chat_history,
        "history_len": len(history),
        "message": body.message,
        "document_id": body.document_id,
        "use_rag": body.use_rag,
        "session_id": session_id,
    }


def _build_context_snippet(
    *,
    user_id: int,
    session_id: int | None,
    document_id: int | None,
    question: str,
    use_rag: bool,
) -> tuple[str, object | None, list]:
    vectorstore = load_vector_db(user_id=user_id, session_id=session_id) if use_rag else None
    docs: list = []
    bits: list[str] = []

    if vectorstore is not None:
        try:
            docs = vectorstore.similarity_search(question, k=4)
            bits.append("\n\n".join(d.page_content for d in docs))
        except Exception:
            docs = []

    if document_id:
        note = get_compiled_note_for_document(document_id, user_id=user_id)
        if note and note.get("markdown"):
            bits.append(note["markdown"][:12000])
        else:
            doc = get_document(document_id, user_id=user_id)
            if doc and doc.get("content"):
                bits.append(doc["content"][:12000])

    return "\n\n".join(b for b in bits if b).strip(), vectorstore, docs


def _chunk_yield(text: str, size: int = 28) -> Generator[str, None, None]:
    if not text:
        return
    for i in range(0, len(text), size):
        yield text[i : i + size]


def _resolve_answer(ctx: dict) -> tuple[Iterable[str], list[str], dict]:
    """Cevap uretici + kaynaklar + meta (researched / note_updated)."""
    user_id = ctx["user_id"]
    model = ctx["model"]
    session_id = ctx.get("session_id")
    document_id = ctx.get("document_id")
    sources: list[str] = []
    meta = {"researched": False, "note_updated": False}

    context, vectorstore, docs = _build_context_snippet(
        user_id=user_id,
        session_id=session_id,
        document_id=document_id,
        question=ctx["message"],
        use_rag=ctx["use_rag"],
    )

    if context and (document_id or vectorstore is not None):
        try:
            assessment = assess_coverage(question=ctx["message"], context=context)
            if assessment.get("on_topic") and not assessment.get("covered"):
                researched = research_and_answer(
                    question=ctx["message"],
                    search_query=assessment.get("search_query") or ctx["message"],
                    topic=assessment.get("topic") or "Ek bilgi",
                )
                note_updated = persist_ek_bilgi(
                    user_id=user_id,
                    document_id=document_id,
                    session_id=session_id,
                    topic=researched["topic"],
                    summary=researched["summary"],
                    answer=researched["answer"],
                    sources=researched["sources"],
                    question=ctx["message"],
                )
                meta["researched"] = True
                meta["note_updated"] = bool(note_updated)
                sources = [
                    (s.get("title") or s.get("href") or "")[:200]
                    for s in (researched.get("sources") or [])
                ]
                return _chunk_yield(researched["answer"]), sources, meta
        except Exception as e:
            print(f"enrichment error: {e}")

    if ctx["use_rag"] and vectorstore is not None:
        token_iter, rag_docs = stream_ai_response(
            model,
            vectorstore,
            ctx["message"],
            chat_history=ctx["chat_history"],
            user_id=user_id,
        )
        sources = [d.page_content[:200] for d in (rag_docs or docs or [])]
        return token_iter, sources, meta

    if document_id:
        doc = get_document(document_id, user_id=user_id)
        note = get_compiled_note_for_document(document_id, user_id=user_id)
        context_bits = []
        if note and note.get("markdown"):
            context_bits.append(note["markdown"][:20000])
        elif doc and doc.get("content"):
            context_bits.append(doc["content"][:20000])
        if context_bits:
            augmented = f"DOKUMAN BAGLAMI:\n{context_bits[0]}\n\nSORU: {ctx['message']}"
            return stream_quick_answer(model, augmented, user_id=user_id), sources, meta

    return stream_quick_answer(model, ctx["message"], user_id=user_id), sources, meta


def _normal_stream(
    ctx: dict, vectorstore, docs: list
) -> tuple[Iterable[str], list[str]]:
    user_id = ctx["user_id"]
    model = ctx["model"]
    document_id = ctx.get("document_id")
    sources: list[str] = []

    if ctx["use_rag"] and vectorstore is not None:
        token_iter, rag_docs = stream_ai_response(
            model,
            vectorstore,
            ctx["message"],
            chat_history=ctx["chat_history"],
            user_id=user_id,
        )
        sources = [d.page_content[:200] for d in (rag_docs or docs or [])]
        return token_iter, sources

    if document_id:
        doc = get_document(document_id, user_id=user_id)
        note = get_compiled_note_for_document(document_id, user_id=user_id)
        context_bits = []
        if note and note.get("markdown"):
            context_bits.append(note["markdown"][:20000])
        elif doc and doc.get("content"):
            context_bits.append(doc["content"][:20000])
        if context_bits:
            augmented = f"DOKUMAN BAGLAMI:\n{context_bits[0]}\n\nSORU: {ctx['message']}"
            return stream_quick_answer(model, augmented, user_id=user_id), sources

    return stream_quick_answer(model, ctx["message"], user_id=user_id), sources


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat/completions", response_model=ChatResponse)
def chat_completions(body: ChatRequest, user: CurrentUser, session: CurrentSession):
    ctx = _prepare_chat(body, user, session)
    user_id = ctx["user_id"]
    conversation_id = ctx["conversation_id"]
    model = ctx["model"]
    memory_note = ctx["memory_note"]

    sources: list[str] = []
    started = time.time()
    error = None
    reply = ""
    researched = False
    note_updated = False

    try:
        token_iter, sources, meta = _resolve_answer(ctx)
        researched = bool(meta.get("researched"))
        note_updated = bool(meta.get("note_updated"))
        reply = "".join(list(token_iter))
        if not reply and body.use_rag:
            vectorstore = load_vector_db(user_id=user_id, session_id=ctx["session_id"])
            if vectorstore is not None:
                reply, docs = get_ai_response(
                    model,
                    vectorstore,
                    body.message,
                    chat_history=ctx["chat_history"],
                    user_id=user_id,
                )
                sources = [d.page_content[:200] for d in (docs or [])]
            else:
                reply = get_quick_answer(model, body.message, user_id=user_id)
    except Exception as e:
        error = str(e)
        reply = f"HATA: {e}"

    latency_ms = int((time.time() - started) * 1000)
    log_model_call(
        model,
        user_id=user_id,
        conversation_id=conversation_id,
        latency_ms=latency_ms,
        error=error,
    )

    if memory_note:
        reply = f"{memory_note}\n\n{reply}"

    create_message(conversation_id, "assistant", reply, user_id=user_id)

    return ChatResponse(
        conversation_id=conversation_id,
        reply=reply,
        sources=sources,
        memory_note=memory_note or None,
        note_updated=note_updated,
        researched=researched,
        title=None,
    )


@router.post("/chat/completions/stream")
def chat_completions_stream(body: ChatRequest, user: CurrentUser, session: CurrentSession):
    ctx = _prepare_chat(body, user, session)
    user_id = ctx["user_id"]
    conversation_id = ctx["conversation_id"]
    model = ctx["model"]
    memory_note = ctx["memory_note"]

    def generate() -> Generator[str, None, None]:
        started = time.time()
        reply_parts: list[str] = []
        sources: list[str] = []
        error = None
        researched = False
        note_updated = False

        yield _sse(
            "meta",
            {
                "conversation_id": conversation_id,
                "memory_note": memory_note or None,
            },
        )

        if memory_note:
            prefix = f"{memory_note}\n\n"
            reply_parts.append(prefix)
            yield _sse("token", {"text": prefix})

        try:
            yield _sse("status", {"text": "Kaynaklar kontrol ediliyor…"})
            context, vectorstore, docs = _build_context_snippet(
                user_id=user_id,
                session_id=ctx.get("session_id"),
                document_id=ctx.get("document_id"),
                question=ctx["message"],
                use_rag=ctx["use_rag"],
            )

            token_iter: Iterable[str]
            if context and (ctx.get("document_id") or vectorstore is not None):
                assessment = assess_coverage(question=ctx["message"], context=context)
                if assessment.get("on_topic") and not assessment.get("covered"):
                    yield _sse(
                        "status",
                        {"text": "Belgede yok — web’de araştırılıyor…"},
                    )
                    researched_payload = research_and_answer(
                        question=ctx["message"],
                        search_query=assessment.get("search_query") or ctx["message"],
                        topic=assessment.get("topic") or "Ek bilgi",
                    )
                    note_updated = bool(
                        persist_ek_bilgi(
                            user_id=user_id,
                            document_id=ctx.get("document_id"),
                            session_id=ctx.get("session_id"),
                            topic=researched_payload["topic"],
                            summary=researched_payload["summary"],
                            answer=researched_payload["answer"],
                            sources=researched_payload["sources"],
                            question=ctx["message"],
                        )
                    )
                    researched = True
                    sources = [
                        (s.get("title") or s.get("href") or "")[:200]
                        for s in (researched_payload.get("sources") or [])
                    ]
                    yield _sse(
                        "status",
                        {"text": "Notlara eklendi — cevap yazılıyor…"},
                    )
                    token_iter = _chunk_yield(researched_payload["answer"])
                else:
                    token_iter, sources = _normal_stream(ctx, vectorstore, docs)
            else:
                token_iter, sources = _normal_stream(ctx, vectorstore, docs)

            for text in token_iter:
                reply_parts.append(text)
                yield _sse("token", {"text": text})
        except Exception as e:
            error = str(e)
            err_text = f"HATA: {e}"
            reply_parts.append(err_text)
            yield _sse("token", {"text": err_text})
            yield _sse("error", {"detail": error})

        reply = "".join(reply_parts)
        latency_ms = int((time.time() - started) * 1000)
        log_model_call(
            model,
            user_id=user_id,
            conversation_id=conversation_id,
            latency_ms=latency_ms,
            error=error,
        )
        create_message(conversation_id, "assistant", reply, user_id=user_id)

        yield _sse(
            "done",
            {
                "conversation_id": conversation_id,
                "sources": sources,
                "memory_note": memory_note or None,
                "researched": researched,
                "note_updated": note_updated,
                "title": None,
            },
        )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
