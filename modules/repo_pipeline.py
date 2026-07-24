"""Compiled notes and pipeline job repository."""

from typing import Optional

from modules.db import get_db, require_user_id, execute_query


@require_user_id
def create_pipeline_job(*, user_id: int, document_id: int, session_id: int = None) -> int:
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO pipeline_jobs (user_id, session_id, document_id, status, current_step)
               VALUES (?, ?, ?, 'queued', 'queued')""",
            (user_id, session_id, document_id),
        )
        conn.commit()
        return cursor.lastrowid


@require_user_id
def get_pipeline_job(job_id: int, *, user_id: int) -> Optional[dict]:
    return execute_query(
        """SELECT id, user_id, document_id, status, current_step, error, created_at, updated_at
           FROM pipeline_jobs WHERE id = ? AND user_id = ?""",
        (job_id, user_id),
        fetch="one",
    )


@require_user_id
def update_pipeline_job(
    job_id: int,
    *,
    user_id: int,
    status: str | None = None,
    current_step: str | None = None,
    error: str | None = None,
) -> bool:
    job = get_pipeline_job(job_id, user_id=user_id)
    if not job:
        return False

    fields = []
    params = []
    if status is not None:
        fields.append("status = ?")
        params.append(status)
    if current_step is not None:
        fields.append("current_step = ?")
        params.append(current_step)
    if error is not None:
        fields.append("error = ?")
        params.append(error)
    fields.append("updated_at = CURRENT_TIMESTAMP")
    params.extend([job_id, user_id])

    with get_db() as conn:
        conn.execute(
            f"UPDATE pipeline_jobs SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
            tuple(params),
        )
        conn.commit()
    return True


@require_user_id
def save_compiled_note(
    *,
    user_id: int,
    document_id: int,
    markdown: str,
    gap_list_json: str = "[]",
    sources_json: str = "[]",
    status: str = "done",
    session_id: int = None,
) -> int:
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO compiled_notes
               (user_id, session_id, document_id, markdown, gap_list_json, sources_json, status)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, session_id, document_id, markdown, gap_list_json, sources_json, status),
        )
        conn.commit()
        return cursor.lastrowid


@require_user_id
def get_compiled_note_for_document(document_id: int, *, user_id: int) -> Optional[dict]:
    return execute_query(
        """SELECT id, user_id, document_id, markdown, gap_list_json, sources_json, status, created_at
           FROM compiled_notes
           WHERE document_id = ? AND user_id = ?
           ORDER BY created_at DESC LIMIT 1""",
        (document_id, user_id),
        fetch="one",
    )
