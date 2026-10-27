import pymupdf

from backend.services.chunking import chunk_pages, format_citation
from backend.services.documents import extract_document_text
from backend.services.sections import clean_heading, is_heading, iter_blocks


def test_heading_rules():
    assert is_heading("# İvme")
    assert is_heading("2.1 Ortalama Hız")
    assert is_heading("SERBEST DÜŞME")
    assert not is_heading("1. adımda hız artar.")
    assert not is_heading("Not: aşağıdaki tabloya bakın:")
    assert clean_heading("## 3.2) Serbest Düşme") == "Serbest Düşme"


def test_iter_blocks_carries_previous_section():
    text = "devam eden metin\n# Yeni Bolum\nicerik"
    blocks = list(iter_blocks(text, current="Eski Bolum"))
    assert [b[2] for b in blocks] == ["Eski Bolum", "Yeni Bolum"]
    assert text[blocks[1][0] : blocks[1][1]].startswith("# Yeni Bolum")


def test_chunks_carry_section_across_pages():
    pages = [
        {"page": 1, "text": "# Hız\nHız birim zamandaki yer değiştirmedir."},
        {"page": 2, "text": "Önceki konunun devamı.\n# İvme\nİvme hız değişimidir."},
    ]
    chunks = chunk_pages(pages, filename="fizik.pdf")
    got = [(c.metadata["page"], c.metadata["section"], c.page_content.split("\n")[0]) for c in chunks]
    assert got == [
        (1, "Hız", "# Hız"),
        (2, "Hız", "Önceki konunun devamı."),
        (2, "İvme", "# İvme"),
    ]
    for c in chunks:  # konum bilgisi bolum bolunmesinden sonra da dogru kalir
        page_text = pages[c.metadata["page"] - 1]["text"]
        start = c.metadata["start_index"]
        assert page_text[start : start + len(c.page_content)] == c.page_content
    assert format_citation(chunks[2]) == "fizik.pdf · s. 2 · İvme"


def test_pdf_large_font_lines_become_headings():
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Newton Yasalari", fontsize=18)  # gomulu font yok: ASCII
    for i, y in enumerate(range(110, 230, 20)):
        page.insert_text((72, y), f"Govde metni satiri {i} biraz uzun bir aciklama.", fontsize=11)
    data = doc.tobytes()
    doc.close()

    text = extract_document_text("ders.pdf", data)["pages"][0]["text"]
    lines = text.splitlines()
    assert lines[0] == "# Newton Yasalari"
    assert not any(line.startswith("#") for line in lines[1:])
