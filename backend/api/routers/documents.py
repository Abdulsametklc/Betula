"""Document upload and listing routes."""

from __future__ import annotations

import os

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from backend.agents.research_graph import run_research_pipeline
from backend.auth.deps import CurrentSession, CurrentUser
from backend.config import get_settings
from backend.schemas import JobOut
from backend.services.documents import extract_document_text
from modules.repo_documents import create_document, delete_document, get_document, get_documents
from modules.repo_pipeline import create_pipeline_job, get_compiled_note_for_document, get_pipeline_job
from modules.repo_sessions import touch_session

router = APIRouter(prefix="/documents", tags=["documents"])


def _run_job(user_id: int, document_id: int, job_id: int, session_id: int | None = None) -> None:
    run_research_pipeline(
        user_id=user_id, document_id=document_id, job_id=job_id, session_id=session_id
    )


@router.get("")
def list_documents(user: CurrentUser, session: CurrentSession):
    return get_documents(user_id=user["id"], session_id=session["id"])


@router.get("/{document_id}")
def get_document_detail(document_id: int, user: CurrentUser, session: CurrentSession):
    doc = get_document(document_id, user_id=user["id"])
    if not doc:
        raise HTTPException(status_code=404, detail="Dokuman bulunamadi")
    if doc.get("session_id") is not None and doc.get("session_id") != session["id"]:
        raise HTTPException(status_code=404, detail="Dokuman bulunamadi")
    return {
        "id": doc["id"],
        "filename": doc["filename"],
        "doc_type": doc.get("doc_type"),
        "upload_date": doc.get("upload_date"),
        "is_processed": doc.get("is_processed"),
        "checksum": doc.get("checksum"),
        "content_length": len(doc.get("content") or ""),
        "session_id": doc.get("session_id"),
    }


@router.post("/upload")
async def upload_document(
    user: CurrentUser,
    session: CurrentSession,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    auto_compile: bool = True,
):
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Bos dosya")

    settings = get_settings()
    os.makedirs(settings.uploads_root, exist_ok=True)

    try:
        parsed = extract_document_text(file.filename or "upload.bin", raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    safe_name = os.path.basename(file.filename or "upload.bin")
    save_path = os.path.join(settings.uploads_root, f"u{user['id']}_s{session['id']}_{safe_name}")
    with open(save_path, "wb") as f:
        f.write(raw)

    doc_id = create_document(
        parsed["filename"],
        parsed["content"],
        parsed["doc_type"],
        user_id=user["id"],
        checksum=parsed["checksum"],
        session_id=session["id"],
    )
    touch_session(session["id"], user_id=user["id"])

    job = None
    if auto_compile:
        job_id = create_pipeline_job(
            user_id=user["id"], document_id=doc_id, session_id=session["id"]
        )
        background_tasks.add_task(_run_job, user["id"], doc_id, job_id, session["id"])
        job = get_pipeline_job(job_id, user_id=user["id"])

    return {
        "document_id": doc_id,
        "filename": parsed["filename"],
        "doc_type": parsed["doc_type"],
        "checksum": parsed["checksum"],
        "job": job,
    }


@router.post("/{document_id}/compile", response_model=JobOut)
def compile_document(
    document_id: int,
    user: CurrentUser,
    session: CurrentSession,
    background_tasks: BackgroundTasks,
):
    doc = get_document(document_id, user_id=user["id"])
    if not doc or (doc.get("session_id") and doc.get("session_id") != session["id"]):
        raise HTTPException(status_code=404, detail="Dokuman bulunamadi")

    job_id = create_pipeline_job(
        user_id=user["id"], document_id=document_id, session_id=session["id"]
    )
    background_tasks.add_task(_run_job, user["id"], document_id, job_id, session["id"])
    touch_session(session["id"], user_id=user["id"])
    job = get_pipeline_job(job_id, user_id=user["id"])
    return JobOut(
        id=job["id"],
        document_id=job["document_id"],
        status=job["status"],
        current_step=job.get("current_step"),
        error=job.get("error"),
        created_at=str(job.get("created_at")) if job.get("created_at") else None,
        updated_at=str(job.get("updated_at")) if job.get("updated_at") else None,
    )


@router.get("/{document_id}/compiled-note")
def get_compiled_note(document_id: int, user: CurrentUser, session: CurrentSession):
    import json

    doc = get_document(document_id, user_id=user["id"])
    if not doc or (doc.get("session_id") and doc.get("session_id") != session["id"]):
        raise HTTPException(status_code=404, detail="Dokuman bulunamadi")

    note = get_compiled_note_for_document(document_id, user_id=user["id"])
    if not note:
        raise HTTPException(status_code=404, detail="Derlenmis not yok")

    gaps = []
    sources = []
    try:
        gaps = json.loads(note.get("gap_list_json") or "[]")
    except Exception:
        gaps = []
    try:
        sources = json.loads(note.get("sources_json") or "[]")
    except Exception:
        sources = []

    return {
        "id": note["id"],
        "document_id": note["document_id"],
        "markdown": note.get("markdown") or "",
        "gap_list": gaps,
        "sources": sources,
        "status": note.get("status"),
        "created_at": note.get("created_at"),
    }


@router.get("/{document_id}/compiled-note/download")
def download_compiled_note(
    document_id: int,
    user: CurrentUser,
    session: CurrentSession,
    format: str = "docx",
    kind: str = "note",
):
    """Download Master Sentez / eksik bilgiler as md|docx|pdf."""
    from fastapi.responses import Response

    from backend.services.export_docs import build_export

    doc = get_document(document_id, user_id=user["id"])
    if not doc or (doc.get("session_id") and doc.get("session_id") != session["id"]):
        raise HTTPException(status_code=404, detail="Dokuman bulunamadi")

    note = get_compiled_note_for_document(document_id, user_id=user["id"])
    if not note:
        raise HTTPException(status_code=404, detail="Derlenmis not yok")

    fmt = (format or "docx").lower().strip()
    if fmt not in {"md", "docx", "pdf"}:
        raise HTTPException(status_code=400, detail="format md|docx|pdf olmali")
    k = (kind or "note").lower().strip()
    if k not in {"note", "gaps", "full"}:
        raise HTTPException(status_code=400, detail="kind note|gaps|full olmali")

    if k in {"note", "full"} and not (note.get("markdown") or "").strip() and k != "gaps":
        raise HTTPException(status_code=404, detail="Derlenmis not yok")

    data, media, filename = build_export(
        note,
        kind=k,
        fmt=fmt,
        doc_title=doc.get("filename"),
    )
    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{document_id}")
def remove_document(document_id: int, user: CurrentUser, session: CurrentSession):
    doc = get_document(document_id, user_id=user["id"])
    if not doc or (doc.get("session_id") and doc.get("session_id") != session["id"]):
        raise HTTPException(status_code=404, detail="Dokuman bulunamadi")
    ok = delete_document(document_id, user_id=user["id"])
    if not ok:
        raise HTTPException(status_code=404, detail="Dokuman bulunamadi")
    return {"ok": True}
