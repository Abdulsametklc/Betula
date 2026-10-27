"""Document text extraction (PyMuPDF + DOCX), page-aware."""

from __future__ import annotations

import hashlib
import io
import os
from typing import BinaryIO, Union

import pymupdf as fitz
from docx import Document

from backend.services.sections import MAX_HEADING_CHARS


FileLike = Union[BinaryIO, bytes]

# Her sayfa: {"page": 1-tabanli sayfa no (DOCX/metin icin None), "text": str}
Page = dict


def get_file_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def checksum_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# Govde metninden en az bu oranda buyuk punto ile yazilmis kisa satirlar baslik sayilir
HEADING_SIZE_RATIO = 1.2


def _pdf_lines(page) -> list[tuple[str, float]]:
    """Sayfadaki satirlar ve her satirin en buyuk punto degeri."""
    lines: list[tuple[str, float]] = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:  # 0 = metin, 1 = gorsel
            continue
        for line in block.get("lines", []):
            spans = [s for s in line.get("spans", []) if s.get("text", "").strip()]
            if spans:
                text = "".join(s["text"] for s in line["spans"]).strip()
                lines.append((text, max(s.get("size", 0) for s in spans)))
    return lines


def _body_font_size(all_lines: list[tuple[str, float]]) -> float:
    """Karakter sayisina gore agirlikli en yaygin punto (govde metni)."""
    weights: dict[float, int] = {}
    for text, size in all_lines:
        key = round(size, 1)
        weights[key] = weights.get(key, 0) + len(text)
    return max(weights, key=weights.get) if weights else 0.0


_BULLETS = ("•", "-", "–", "*", "▪", "●", "○", "◦", "")  # : Word/PowerPoint Symbol fontu madde isareti


def _mark_headings(lines: list[tuple[str, float]], threshold: float) -> list[str]:
    """Esigi asan satirlari ``# Baslik`` yapar; ayni puntodaki ardisik baslik satirlarini birlestirir."""
    out: list[str] = []
    prev_size = None
    for text, size in lines:
        is_heading = (
            threshold
            and size >= threshold
            and not text.startswith(_BULLETS + ("#",))
        )
        if is_heading and prev_size == size and len(out[-1]) + len(text) < MAX_HEADING_CHARS:
            out[-1] = f"{out[-1]} {text}"  # iki satira tasan baslik
            continue
        out.append(f"# {text}" if is_heading and len(text) <= MAX_HEADING_CHARS else text)
        prev_size = size if is_heading else None
    return out


def get_pdf_pages_from_bytes(data: bytes) -> list[Page]:
    """Sayfa bazli metin; govdeden belirgin buyuk puntolu kisa satirlar ``# Baslik`` olur.

    Esik hem belgenin hem sayfanin govde puntosuna gore alinir; boylece slaytlarda buyuk
    yazilmis govde metni baslik sanilmaz.
    """
    with fitz.open(stream=data, filetype="pdf") as doc:
        page_lines = [(index, _pdf_lines(page)) for index, page in enumerate(doc, start=1)]

    doc_body = _body_font_size([ln for _, lines in page_lines for ln in lines])
    pages: list[Page] = []
    for index, lines in page_lines:
        threshold = max(doc_body, _body_font_size(lines)) * HEADING_SIZE_RATIO
        page_text = "\n".join(_mark_headings(lines, threshold)).strip()
        if page_text:
            pages.append({"page": index, "text": page_text})
    return pages


def get_pdf_text_from_bytes(data: bytes) -> str:
    return pages_to_text(get_pdf_pages_from_bytes(data))


def get_docx_text_from_bytes(data: bytes) -> str:
    text = ""
    doc = Document(io.BytesIO(data))
    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            text += paragraph.text + "\n"
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    text += cell.text + "\n"
    return text.strip()


def pages_to_text(pages: list[Page]) -> str:
    return "\n".join(p["text"] for p in pages if p.get("text")).strip()


def extract_document_text(filename: str, data: bytes) -> dict:
    extension = get_file_extension(filename)
    if extension == ".pdf":
        pages = get_pdf_pages_from_bytes(data)
        doc_type = "pdf"
    elif extension == ".docx":
        # DOCX'te sabit sayfa yok; tek mantiksal sayfa olarak tutulur
        docx_text = get_docx_text_from_bytes(data)
        pages = [{"page": None, "text": docx_text}] if docx_text else []
        doc_type = "docx"
    elif extension == ".doc":
        raise ValueError("Eski .doc formati desteklenmiyor; lutfen .docx veya .pdf olarak kaydedin")
    else:
        raise ValueError(f"Desteklenmeyen dosya formati: {extension}")

    content = pages_to_text(pages)
    if not content:
        raise ValueError("Dokumandan metin cikarilamadi")

    return {
        "filename": filename,
        "content": content,
        "pages": pages,
        "doc_type": doc_type,
        "checksum": checksum_bytes(data),
    }
