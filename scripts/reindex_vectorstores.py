"""Vektor indekslerini sayfa ve bolum bilgisiyle yeniden kurar.

Faz 0 oncesi yuklenen belgelerin parcalarinda sayfa/bolum bilgisi yoktu ve ayni oturumdaki
ikinci belge ilkini indeksten siliyordu. Bu betik:

1. Sayfa bilgisi olmayan belgeler icin, kayitli yukleme dosyasi varsa sayfalari yeniden cikarir
   ve ``documents.pages_json`` alanina yazar (dosya yoksa tum metin tek sayfa kabul edilir).
2. Her (kullanici, oturum) icin indeksi sifirdan kurar: islenmis tum belgeler + Master Sentez notlari.
3. Eski indeksi silmez; ``<klasor>.bak-<zaman>`` olarak yedekler.

    python scripts/reindex_vectorstores.py --dry-run      # ne yapilacagini goster
    python scripts/reindex_vectorstores.py                # uygula
    python scripts/reindex_vectorstores.py --user-id 2    # tek kullanici
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.config import get_settings  # noqa: E402
from backend.services.chunking import (  # noqa: E402
    SOURCE_COMPILED_NOTE,
    chunk_id_prefix,
    chunk_pages,
    chunk_text,
)
from backend.services.documents import extract_document_text  # noqa: E402
from backend.services.vectorstore import index_chunks, user_vectorstore_path  # noqa: E402
from modules.db import execute_query, init_db  # noqa: E402
from modules.repo_documents import get_document_pages, set_document_pages  # noqa: E402
from modules.repo_pipeline import get_compiled_note_for_document  # noqa: E402


def find_upload(doc: dict) -> Path | None:
    root = Path(get_settings().uploads_root)
    name = os.path.basename(doc["filename"] or "")
    for candidate in (f"u{doc['user_id']}_s{doc['session_id']}_{name}", f"u{doc['user_id']}_{name}"):
        if (root / candidate).is_file():
            return root / candidate
    return None


def backfill_pages(doc: dict, dry_run: bool) -> str:
    if doc.get("pages_json"):
        return "sayfa bilgisi var"
    path = find_upload(doc)
    if path is None:
        return "yukleme dosyasi yok -> tek sayfa"
    try:
        pages = extract_document_text(path.name, path.read_bytes())["pages"]
    except ValueError as e:
        return f"okunamadi ({e}) -> tek sayfa"
    if not dry_run:
        set_document_pages(doc["id"], pages, user_id=doc["user_id"])
    doc["pages_json"] = json.dumps(pages, ensure_ascii=False)  # dry-run'da da plan dogru gorunsun
    return f"{len(pages)} sayfa dosyadan cikarildi"


def build_chunks(doc: dict) -> list:
    chunks = chunk_pages(get_document_pages(doc), document_id=doc["id"], filename=doc["filename"])
    note = get_compiled_note_for_document(doc["id"], user_id=doc["user_id"])
    if note and note.get("markdown"):
        chunks += chunk_text(
            note["markdown"], document_id=doc["id"], filename=doc["filename"], source=SOURCE_COMPILED_NOTE
        )
    return chunks


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--user-id", type=int)
    args = ap.parse_args()

    init_db()  # yeni kolonlarin (pages_json) var oldugundan emin ol
    sql = "SELECT id, user_id, session_id, filename, content, pages_json FROM documents WHERE is_processed = 1"
    params: tuple = ()
    if args.user_id:
        sql += " AND user_id = ?"
        params = (args.user_id,)
    docs = [dict(r) for r in execute_query(sql, params, fetch="all")]

    groups: dict[tuple, list[dict]] = defaultdict(list)
    for doc in docs:
        groups[(doc["user_id"], doc["session_id"])].append(doc)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for (user_id, session_id), group in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1] or 0)):
        path = Path(user_vectorstore_path(user_id, session_id))
        print(f"\n== kullanici {user_id}, oturum {session_id} -> {path}")
        plan = []
        for doc in group:
            status = backfill_pages(doc, args.dry_run)
            chunks = build_chunks(doc)
            pages = sorted({c.metadata["page"] for c in chunks if c.metadata["page"] is not None})
            sections = {c.metadata["section"] for c in chunks if c.metadata["section"]}
            print(f"  belge {doc['id']} ({doc['filename']}): {status}; {len(chunks)} parca, "
                  f"{len(pages)} sayfa, {len(sections)} bolum")
            plan.append((doc, chunks))

        if args.dry_run:
            continue
        if (path / "index.faiss").exists():
            backup = path.with_name(f"{path.name}.bak-{stamp}")
            shutil.move(str(path), str(backup))
            print(f"  eski indeks yedeklendi: {backup}")
        for doc, chunks in plan:
            index_chunks(chunks, user_id=user_id, session_id=session_id, id_prefix=chunk_id_prefix(doc["id"]))
        print("  indeks yeniden kuruldu")

    if args.dry_run:
        print("\n(dry-run: hicbir sey degistirilmedi)")


if __name__ == "__main__":
    main()
