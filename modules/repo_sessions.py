"""Study sessions repository — çalışma oturumları."""

from __future__ import annotations

from typing import Optional

from modules.db import execute_query, get_db, require_user_id


@require_user_id
def create_session(*, user_id: int, title: str = "Yeni Çalışma", description: str = "") -> int:
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO study_sessions (user_id, title, description)
               VALUES (?, ?, ?)""",
            (user_id, (title or "Yeni Çalışma").strip()[:80], (description or "").strip()[:280]),
        )
        conn.commit()
        return cursor.lastrowid


@require_user_id
def list_sessions(*, user_id: int, limit: int = 100) -> list:
    return execute_query(
        """SELECT s.id, s.title, s.description, s.created_at, s.updated_at,
                  (SELECT COUNT(*) FROM documents d WHERE d.session_id = s.id AND d.user_id = s.user_id) AS doc_count,
                  (SELECT COUNT(*) FROM conversations c WHERE c.session_id = s.id AND c.user_id = s.user_id) AS chat_count,
                  (SELECT COUNT(*) FROM quiz_attempts q WHERE q.session_id = s.id AND q.user_id = s.user_id) AS quiz_count
           FROM study_sessions s
           WHERE s.user_id = ? AND s.is_active = 1
           ORDER BY s.updated_at DESC
           LIMIT ?""",
        (user_id, limit),
        fetch="all",
    )


@require_user_id
def get_session(session_id: int, *, user_id: int) -> Optional[dict]:
    return execute_query(
        """SELECT id, user_id, title, description, is_active, created_at, updated_at
           FROM study_sessions WHERE id = ? AND user_id = ? AND is_active = 1""",
        (session_id, user_id),
        fetch="one",
    )


@require_user_id
def update_session(
    session_id: int,
    *,
    user_id: int,
    title: str | None = None,
    description: str | None = None,
) -> bool:
    sess = get_session(session_id, user_id=user_id)
    if not sess:
        return False
    fields = ["updated_at = datetime('now')"]
    params: list = []
    if title is not None:
        fields.append("title = ?")
        params.append(title.strip()[:80] or "Yeni Çalışma")
    if description is not None:
        fields.append("description = ?")
        params.append(description.strip()[:280])
    params.extend([session_id, user_id])
    with get_db() as conn:
        conn.execute(
            f"UPDATE study_sessions SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
            tuple(params),
        )
        conn.commit()
    return True


@require_user_id
def touch_session(session_id: int, *, user_id: int) -> None:
    with get_db() as conn:
        conn.execute(
            """UPDATE study_sessions SET updated_at = datetime('now')
               WHERE id = ? AND user_id = ?""",
            (session_id, user_id),
        )
        conn.commit()


@require_user_id
def delete_session(session_id: int, *, user_id: int) -> bool:
    """Soft-delete. En az bir aktif oturum kalmali."""
    with get_db() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM study_sessions WHERE user_id = ? AND is_active = 1",
            (user_id,),
        ).fetchone()[0]
        if count <= 1:
            return False
        cursor = conn.execute(
            """UPDATE study_sessions SET is_active = 0, updated_at = datetime('now')
               WHERE id = ? AND user_id = ? AND is_active = 1""",
            (session_id, user_id),
        )
        conn.commit()
        return cursor.rowcount > 0


@require_user_id
def get_or_create_default_session(*, user_id: int) -> dict:
    rows = list_sessions(user_id=user_id, limit=1)
    if rows:
        return get_session(rows[0]["id"], user_id=user_id) or rows[0]
    sid = create_session(user_id=user_id, title="Genel Çalışma", description="")
    return get_session(sid, user_id=user_id)
