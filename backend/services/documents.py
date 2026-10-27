"""Document text extraction (PyMuPDF + DOCX), page-aware."""

from __future__ import annotations

import hashlib
import io
import os
from typing import BinaryIO, Union

from docx import Document

from backend.services.pdf_reader import read_pdf_pages


FileLike = Union[BinaryIO, bytes]

# Her sayfa: {"page": 1-tabanli sayfa no (DOCX/metin icin None), "text": str,
#             "slides": [[metin_ofseti, "1.5"], ...] (yalnizca slayt PDF'lerinde)}
Page = dict


def get_file_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def checksum_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def get_pdf_pages_from_bytes(data: bytes) -> list[Page]:
    """Sayfa bazli metin; basliklar ``# Baslik``, slayt numaralari ``slides`` alaninda.

    Ayrintilar: :mod:`backend.services.pdf_reader`
    """
    return read_pdf_pages(data)


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
