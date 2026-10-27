import io

import pytest
from docx import Document

from backend.services.documents import extract_document_text


def test_pdf_pages_keep_page_numbers(make_pdf):
    data = make_pdf(["Birinci sayfa: kuvvet", "", "Ucuncu sayfa: enerji"])
    parsed = extract_document_text("ders.pdf", data)

    assert parsed["doc_type"] == "pdf"
    # Bos sayfa atlanir ama sayfa numaralari kaymaz
    assert [p["page"] for p in parsed["pages"]] == [1, 3]
    assert "kuvvet" in parsed["pages"][0]["text"]
    assert "enerji" in parsed["pages"][1]["text"]
    assert "kuvvet" in parsed["content"] and "enerji" in parsed["content"]
    assert len(parsed["checksum"]) == 64


def test_docx_is_single_logical_page():
    buf = io.BytesIO()
    doc = Document()
    doc.add_paragraph("Hucre zari secici gecirgendir.")
    doc.save(buf)

    parsed = extract_document_text("not.docx", buf.getvalue())
    assert parsed["doc_type"] == "docx"
    assert parsed["pages"] == [{"page": None, "text": "Hucre zari secici gecirgendir."}]


def test_legacy_doc_is_rejected_with_clear_message():
    with pytest.raises(ValueError, match=r"\.docx"):
        extract_document_text("eski.doc", b"\xd0\xcf\x11\xe0")


def test_empty_pdf_is_rejected(make_pdf):
    with pytest.raises(ValueError):
        extract_document_text("bos.pdf", make_pdf([""]))
