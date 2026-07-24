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
    delete_conversation,
    get_conversation,
    get_messages,
    list_conversations,
    log_model_call,
    update_conversation,
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
    conv = get_conversation(conversation_id, user_id=user["id"])
    if not conv or (conv.get("session_id") and conv.get("session_id") != session["id"]):
        raise HTTPException(status_code=404, detail="Sohbet bulunamadi")
    ok = delete_conversation(conversation_id, user_id=user["id"])
    if not ok:
        raise HTTPException(status_code=404, detail="Sohbet bulunamadi")
    return {"ok": True}


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
        title = body.message[:60] + ("…" if len(body.message) > 60 else "")
        conversation_id = create_conversation(
            user_id=user_id,
            title=title or "Yeni Sohbet",
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


def _resolve_stream(ctx: dict) -> tuple[Iterable[str], list[str]]:
    """LLM token akisini ve kaynak listesini dondurur."""
    user_id = ctx["user_id"]
    model = ctx["model"]
    session_id = ctx.get("session_id")
    sources: list[str] = []

    vectorstore = (
        load_vector_db(user_id=user_id, session_id=session_id) if ctx["use_rag"] else None
    )

    if ctx["use_rag"] and vectorstore is not None:
        token_iter, docs = stream_ai_response(
            model,
            vectorstore,
            ctx["message"],
            chat_history=ctx["chat_history"],
            user_id=user_id,
        )
        sources = [d.page_content[:200] for d in (docs or [])]
        return token_iter, sources

    if ctx["document_id"]:
        doc = get_document(ctx["document_id"], user_id=user_id)
        note = get_compiled_note_for_document(ctx["document_id"], user_id=user_id)
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
    session_id = ctx["session_id"]

    sources: list[str] = []
    started = time.time()
    error = None
    reply = ""

    try:
        vectorstore = (
            load_vector_db(user_id=user_id, session_id=session_id) if body.use_rag else None
        )

        if body.use_rag and vectorstore is not None:
            reply, docs = get_ai_response(
                model,
                vectorstore,
                body.message,
                chat_history=ctx["chat_history"],
                user_id=user_id,
            )
            sources = [d.page_content[:200] for d in (docs or [])]
        elif body.document_id:
            doc = get_document(body.document_id, user_id=user_id)
            note = get_compiled_note_for_document(body.document_id, user_id=user_id)
            context_bits = []
            if note and note.get("markdown"):
                context_bits.append(note["markdown"][:20000])
            elif doc and doc.get("content"):
                context_bits.append(doc["content"][:20000])
            if context_bits:
                augmented = (
                    f"DOKUMAN BAGLAMI:\n{context_bits[0]}\n\nSORU: {body.message}"
                )
                reply = get_quick_answer(model, augmented, user_id=user_id)
            else:
                reply = get_quick_answer(model, body.message, user_id=user_id)
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

    if ctx["history_len"] <= 1:
        update_conversation(
            conversation_id,
            user_id=user_id,
            title=body.message[:60] + ("…" if len(body.message) > 60 else ""),
        )

    return ChatResponse(
        conversation_id=conversation_id,
        reply=reply,
        sources=sources,
        memory_note=memory_note or None,
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
            token_iter, sources = _resolve_stream(ctx)
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

        if ctx["history_len"] <= 1:
            update_conversation(
                conversation_id,
                user_id=user_id,
                title=body.message[:60] + ("…" if len(body.message) > 60 else ""),
            )

        yield _sse(
            "done",
            {
                "conversation_id": conversation_id,
                "sources": sources,
                "memory_note": memory_note or None,
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
