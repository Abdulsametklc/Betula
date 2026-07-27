"""Compiled notes and pipeline job repository."""

import json
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
        """SELECT id, user_id, document_id, markdown, gap_list_json, sources_json, status, created_at, session_id
           FROM compiled_notes
           WHERE document_id = ? AND user_id = ?
           ORDER BY created_at DESC LIMIT 1""",
        (document_id, user_id),
        fetch="one",
    )


@require_user_id
def append_ek_bilgi_to_compiled_note(
    *,
    user_id: int,
    document_id: int,
    markdown_block: str,
    gap_item: dict | None = None,
    session_id: int | None = None,
) -> bool:
    """Master Sentez markdown'ina 'Ek Bilgiler' bolumu ekler / gunceller."""
    note = get_compiled_note_for_document(document_id, user_id=user_id)
    section_header = "## Ek Bilgiler"
    block = (markdown_block or "").strip()
    if not block:
        return False

    if note:
        md = note.get("markdown") or ""
        if section_header in md:
            md = md.rstrip() + "\n\n" + block + "\n"
        else:
            md = md.rstrip() + f"\n\n---\n\n{section_header}\n\n" + block + "\n"

        gaps = []
        try:
            gaps = json.loads(note.get("gap_list_json") or "[]")
        except Exception:
            gaps = []
        if not isinstance(gaps, list):
            gaps = []
        if gap_item:
            # Ayni konu basligi varsa ozetini guncelle, yoksa ekle
            topic = (gap_item.get("topic") or "").strip().lower()
            replaced = False
            for i, g in enumerate(gaps):
                if str(g.get("topic") or "").strip().lower() == topic and topic:
                    gaps[i] = {**g, **gap_item}
                    replaced = True
                    break
            if not replaced:
                gaps.append(gap_item)

        with get_db() as conn:
            conn.execute(
                """UPDATE compiled_notes
                   SET markdown = ?, gap_list_json = ?
                   WHERE id = ? AND user_id = ?""",
                (md, json.dumps(gaps, ensure_ascii=False), note["id"], user_id),
            )
            conn.commit()
        return True

    # Not yoksa yeni derlenmis not olustur
    gaps = [gap_item] if gap_item else []
    md = f"{section_header}\n\n{block}\n"
    save_compiled_note(
        user_id=user_id,
        document_id=document_id,
        markdown=md,
        gap_list_json=json.dumps(gaps, ensure_ascii=False),
        sources_json="[]",
        status="done",
        session_id=session_id,
    )
    return True
