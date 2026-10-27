"""Degerlendirme korpusunu yukler.

Klasor yapisi (her dokuman bir klasor)::

    evaluation/data/corpus/<doc_id>/
        meta.json          # {"title", "course", "language", "license", "notes"}
        source.pdf | source.docx | source.md | source.txt
    evaluation/data/private/<doc_id>/   # ayni yapi; telifli materyal, git'e girmez
    evaluation/data/qa/<doc_id>.jsonl   # bilgi getirme sorulari (istege bagli)

Metin kaynaklarinda sayfa sinirlari ``<!-- page: N -->`` satiriyla belirtilir.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from backend.services.documents import extract_document_text

DATA_DIR = Path(__file__).resolve().parent / "data"
CORPUS_DIRS = (DATA_DIR / "corpus", DATA_DIR / "private")
QA_DIR = DATA_DIR / "qa"
GENERATED_DIR = DATA_DIR / "generated"

_PAGE_MARKER = re.compile(r"^\s*<!--\s*page:\s*(\d+)\s*-->\s*$", re.MULTILINE)


@dataclass
class CorpusDocument:
    doc_id: str
    filename: str
    pages: list[dict]
    meta: dict = field(default_factory=dict)


def parse_marked_text(text: str) -> list[dict]:
    """``<!-- page: N -->`` isaretli metni sayfalara boler; isaret yoksa tek sayfa."""
    marks = list(_PAGE_MARKER.finditer(text))
    if not marks:
        body = text.strip()
        return [{"page": None, "text": body}] if body else []
    pages = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[m.end() : end].strip()
        if body:
            pages.append({"page": int(m.group(1)), "text": body})
    return pages


def load_source(path: Path) -> list[dict]:
    if path.suffix.lower() in (".md", ".txt"):
        return parse_marked_text(path.read_text(encoding="utf-8"))
    return extract_document_text(path.name, path.read_bytes())["pages"]


def load_document(folder: Path) -> CorpusDocument:
    sources = sorted(folder.glob("source.*"))
    if not sources:
        raise FileNotFoundError(f"{folder} icinde source.* yok")
    meta_path = folder / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    return CorpusDocument(
        doc_id=folder.name,
        filename=meta.get("filename") or sources[0].name,
        pages=load_source(sources[0]),
        meta=meta,
    )


def iter_corpus(only: list[str] | None = None) -> list[CorpusDocument]:
    docs = []
    for root in CORPUS_DIRS:
        if not root.exists():
            continue
        for folder in sorted(p for p in root.iterdir() if p.is_dir()):
            if only and folder.name not in only:
                continue
            docs.append(load_document(folder))
    return docs


def load_qa(doc_id: str) -> list[dict]:
    """Her satir: {"question": str, "evidence_pages": [int, ...], "answer": str (istege bagli)}"""
    path = QA_DIR / f"{doc_id}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
