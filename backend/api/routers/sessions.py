"""Study session routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.auth.deps import CurrentUser
from modules.repo_sessions import (
    create_session,
    delete_session,
    get_session,
    list_sessions,
    touch_session,
    update_session,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionCreate(BaseModel):
    title: str = Field(default="Yeni Çalışma", max_length=80)
    description: str = Field(default="", max_length=280)


class SessionUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=280)


@router.get("")
def sessions_list(user: CurrentUser):
    return list_sessions(user_id=user["id"])


@router.post("")
def sessions_create(body: SessionCreate, user: CurrentUser):
    sid = create_session(
        user_id=user["id"],
        title=body.title,
        description=body.description,
    )
    sess = get_session(sid, user_id=user["id"])
    return sess


@router.get("/{session_id}")
def sessions_get(session_id: int, user: CurrentUser):
    sess = get_session(session_id, user_id=user["id"])
    if not sess:
        raise HTTPException(status_code=404, detail="Oturum bulunamadi")
    return sess


@router.patch("/{session_id}")
def sessions_update(session_id: int, body: SessionUpdate, user: CurrentUser):
    ok = update_session(
        session_id,
        user_id=user["id"],
        title=body.title,
        description=body.description,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Oturum bulunamadi")
    return get_session(session_id, user_id=user["id"])


@router.post("/{session_id}/touch")
def sessions_touch(session_id: int, user: CurrentUser):
    sess = get_session(session_id, user_id=user["id"])
    if not sess:
        raise HTTPException(status_code=404, detail="Oturum bulunamadi")
    touch_session(session_id, user_id=user["id"])
    return {"ok": True}


@router.delete("/{session_id}")
def sessions_delete(session_id: int, user: CurrentUser):
    ok = delete_session(session_id, user_id=user["id"])
    if not ok:
        raise HTTPException(
            status_code=400,
            detail="Oturum silinemedi. En az bir aktif oturum kalmalı.",
        )
    return {"ok": True}
