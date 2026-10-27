"""Slayt PDF'leri icin okuyucu davranisi (gomulu font olmadigindan metinler ASCII)."""

import pymupdf
import pytest

from backend.services.chunking import chunk_pages, format_citation
from backend.services.documents import extract_document_text
from backend.services.pdf_reader import heading_text_ok

HEADER = "Sayisal Devreler (Lojik Devreleri)"
FOOTER = "2000-2020 Feza BUZLUCA"
BODY = "Bu satir slaytin govde metnidir ve yeterince uzun bir aciklamadir."


def _slide(page, top: float, label: str, title: str, extra: list[tuple[str, str, float]] = ()):
    """Sayfanin bir yarisina slayt cizer. Baslik bilerek govdeden SONRA yazilir (okuma sirasi testi)."""
    page.insert_text((72, top), HEADER, fontsize=7)
    y = top + 40
    for i in range(3):  # gercek slaytlardaki gibi her satir farkli (tekrar eden satir = altbilgi)
        page.insert_text((72, y), f"{BODY} [{label}.{i}]", fontsize=9)
        y += 14
    for text, font, size in extra:
        page.insert_text((72, y), text, fontname=font, fontsize=size)
        y += 14
    page.insert_text((72, top + 20), title, fontname="hebo", fontsize=10)  # kalin, govdenin ~1.1 kati
    page.insert_text((120, top + 300), FOOTER, fontsize=6)
    page.insert_text((470, top + 300), label, fontsize=7)


@pytest.fixture
def slide_pdf() -> bytes:
    doc = pymupdf.open()
    titles = iter(["Ikili Kodlama", "Gray Kodu", "Hamming Uzakligi", "Karnaugh Diyagramlari (devami)",
                   "Tam Toplayici", "Veri Seciciler"])
    for p in range(3):
        page = doc.new_page()
        _slide(page, 60, f"1.{2 * p + 1}", next(titles),
               extra=[("8 bit +5", "hebo", 10), ("Ornek: 4 bitlik toplama", "hebo", 10)])
        _slide(page, 420, f"1.{2 * p + 2}", next(titles), extra=[("F = A + B", "hebo", 14)])
    data = doc.tobytes()
    doc.close()
    return data


def test_bold_slide_titles_become_headings_in_reading_order(slide_pdf):
    page = extract_document_text("ders.pdf", slide_pdf)["pages"][0]
    lines = page["text"].splitlines()
    assert lines[0] == "# Ikili Kodlama"  # baslik PDF'te govdeden sonra yazilmisti
    assert "# Gray Kodu" in lines
    headings = [ln for ln in lines if ln.startswith("#")]
    assert headings == ["# Ikili Kodlama", "# Gray Kodu"]  # "8 bit +5", "Ornek:", formul baslik degil


def test_headers_footers_and_slide_numbers_are_removed(slide_pdf):
    for page in extract_document_text("ders.pdf", slide_pdf)["pages"]:
        assert HEADER not in page["text"]
        assert FOOTER not in page["text"]
        assert not any(ln.strip() in {"1.1", "1.2", "1.3"} for ln in page["text"].splitlines())


def test_slide_labels_with_offsets(slide_pdf):
    pages = extract_document_text("ders.pdf", slide_pdf)["pages"]
    assert [label for p in pages for _, label in p["slides"]] == ["1.1", "1.2", "1.3", "1.4", "1.5", "1.6"]
    first = pages[0]
    second_offset = first["slides"][1][0]
    assert first["text"][second_offset:].startswith("# Gray Kodu")


def test_chunks_and_citation_carry_slide(slide_pdf):
    chunks = chunk_pages(extract_document_text("ders.pdf", slide_pdf)["pages"], filename="ders.pdf")
    gray = next(c for c in chunks if c.metadata["section"] == "Gray Kodu")
    assert gray.metadata["slide"] == "1.2"
    assert format_citation(gray) == "ders.pdf · s. 1 / slayt 1.2 · Gray Kodu"
    # "(devami)" eki bolum adindan atilir
    assert any(c.metadata["section"] == "Karnaugh Diyagramlari" for c in chunks)
    # parca hicbir zaman iki slayta tasmaz
    for c in chunks:
        assert not ("Ikili Kodlama" in c.page_content and "Gray Kodu" in c.page_content)


@pytest.mark.parametrize(
    "text, ok",
    [
        ("Gray Kodu", True),
        ("2.1 Ortalama Hiz", True),
        ("Veri Seciciler (Multiplexer):", True),
        ("8 bit +5", False),
        ("10000001: Gosterilemiyor", False),
        ("F1 = A C' + A B", False),
        ("Ornek: 4 bitlik toplama", False),
        ("veya", False),
        ("Taşma vardır.", False),
        ("Doç.Dr. Feza BUZLUCA", False),
        ("Bir sütun başka bir sütunu örtüyorsa örten sütun (daha", False),
        ("1. Adım: Bu tabloda 9 ve 15 başlıca noktalardır. A ve D gerekli", False),
        ("• Madde isaretli satir", False),
    ],
)
def test_heading_text_rules(text, ok):
    assert heading_text_ok(text) is ok
