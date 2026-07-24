"""Memory and preferences routes."""

from fastapi import APIRouter, HTTPException

from backend.auth.deps import CurrentUser
from backend.schemas import MemoryEnabledRequest, MemoryUpsertRequest
from modules.repo_memory import (
    clear_all_memory,
    delete_memory,
    is_memory_enabled,
    list_memory,
    set_memory_enabled,
    upsert_memory,
)

router = APIRouter(tags=["memory"])


@router.get("/memory")
def memory_list(user: CurrentUser, category: str | None = None):
    return list_memory(user_id=user["id"], category=category, active_only=True)


@router.put("/memory")
def memory_upsert(body: MemoryUpsertRequest, user: CurrentUser):
    mid = upsert_memory(
        body.category,
        body.key,
        body.value,
        user_id=user["id"],
        confidence=body.confidence,
        importance=body.importance,
    )
    return {"id": mid, "ok": True}


@router.delete("/memory/{key}")
def memory_delete(key: str, user: CurrentUser, category: str | None = None):
    ok = delete_memory(key, user_id=user["id"], category=category)
    if not ok:
        raise HTTPException(status_code=404, detail="Kayit bulunamadi")
    return {"ok": True}


@router.delete("/memory")
def memory_clear(user: CurrentUser):
    n = clear_all_memory(user_id=user["id"])
    return {"ok": True, "cleared": n}


@router.get("/preferences/memory")
def memory_pref_get(user: CurrentUser):
    return {"enabled": is_memory_enabled(user["id"])}


@router.patch("/preferences/memory")
def memory_pref_set(body: MemoryEnabledRequest, user: CurrentUser):
    set_memory_enabled(user["id"], body.enabled)
    return {"enabled": body.enabled}
