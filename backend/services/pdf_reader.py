"""Duzen farkinda PDF okuyucu: ders notu ve slayt PDF'leri icin.

Her sayfa icin su islemler yapilir:

1. **Okuma sirasi:** metin bloklari sayfadaki dikey konumuna gore siralanir (PDF icindeki
   yazim sirasi cogu zaman gorsel siradan farklidir; or. slayt basligi govdeden sonra gelir).
2. **Ust/alt bilgi temizligi:** sayfalarin cogunda tekrar eden kucuk puntolu satirlar
   (ders adi, URL, telif satiri) atilir.
3. **Slayt numarasi:** "1.5" gibi slayt numaralari metinden cikarilip ``slides`` alanina
   konum bilgisiyle yazilir; boylece kaynak "slayt 1.5" olarak gosterilebilir.
4. **Basliklar:** govdeden belirgin buyuk ya da kalin ve hafif buyuk kisa satirlar
   ``# Baslik`` olarak isaretlenir; sayisal ornek satirlari ve "Ornek:" gibi etiketler elenir.

Cikti: ``{"page": int, "text": str, "slides": [[baslangic_ofseti, "1.5"], ...]}``
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Optional

import pymupdf

from backend.services.sections import MAX_HEADING_CHARS, looks_like_title

# Govdeden en az bu oranda buyuk kisa satirlar baslik sayilir
HEADING_SIZE_RATIO = 1.2
# Kalin satirlar icin daha dusuk esik (slaytlarda baslik cogu zaman yalnizca ~1.1 kat buyuk)
BOLD_HEADING_SIZE_RATIO = 1.05
# Ust/alt bilgi: govdeden kucuk ve sayfalarin en az bu oraninda (ve en az 3 sayfada)
# tekrar eden satirlar. Dusuk oran, birkac sayfada bir tekrar eden lisans satirlarini da yakalar.
REPEATED_LINE_PAGE_RATIO = 0.25
SMALL_TEXT_RATIO = 0.9

BULLETS = ("•", "-", "–", "*", "▪", "●", "○", "◦", "►", "➢", "✓")
_SLIDE_LABEL = re.compile(r"^\d{1,3}(\.\d{1,3})?$")
_DOTTED_LABEL = re.compile(r"^\d{1,3}\.\d{1,3}$")
_NUMBERED_TITLE = re.compile(r"^\d+(\.\d+)*[.)]?\s+[A-ZÇĞİÖŞÜ]")


@dataclass
class Line:
    text: str
    size: float
    bold: bool
    x: float
    y: float


def _clean_text(text: str) -> str:
    """Sembol fontlarinin ozel alan (PUA) karakterlerini temizler; satir basindakini madde isareti yapar."""
    if not text:
        return text
    head = "• " if "" <= text[0] <= "" else ""
    body = "".join(ch for ch in text if not ("" <= ch <= ""))
    return (head + body.strip()).strip()


def _is_bold(span: dict) -> bool:
    font = span.get("font", "")
    return bool(span.get("flags", 0) & 16) or any(k in font for k in ("Bold", "Black", "Heavy"))


def _page_lines(page) -> list[Line]:
    """Metin satirlari, bloklarin sayfadaki konumuna gore (ust -> alt, sol -> sag) sirali."""
    blocks = [b for b in page.get_text("dict").get("blocks", []) if b.get("type") == 0]
    blocks.sort(key=lambda b: (round(b["bbox"][1]), b["bbox"][0]))
    lines: list[Line] = []
    for block in blocks:
        for line in block.get("lines", []):
            spans = [s for s in line.get("spans", []) if s.get("text", "").strip()]
            if not spans:
                continue
            text = _clean_text("".join(s["text"] for s in line["spans"]).strip())
            if not text:
                continue
            chars = sum(len(s["text"].strip()) for s in spans)
            bold_chars = sum(len(s["text"].strip()) for s in spans if _is_bold(s))
            lines.append(
                Line(
                    text=text,
                    size=max(s.get("size", 0) for s in spans),
                    bold=chars > 0 and bold_chars / chars >= 0.8,
                    x=line["bbox"][0],
                    y=line["bbox"][1],
                )
            )
    return lines


def _body_size(lines: list[Line]) -> float:
    """Govde puntosu: cumle uzunlugundaki normal satirlarin en yaygin puntosu.

    Kisa satirlar (sekil etiketleri, tablo hucreleri) hesaba katilmaz; aksi halde cizim
    agirlikli belgelerde govde gercekte oldugundan kucuk hesaplanir.
    """
    def mode(candidates: list[Line]) -> float:
        weights: Counter = Counter()
        for ln in candidates:
            weights[round(ln.size, 1)] += len(ln.text)
        return weights.most_common(1)[0][0] if weights else 0.0

    sentences = [ln for ln in lines if len(ln.text) >= 25 and not ln.bold]
    return mode(sentences) or mode(lines)


def _frequent_lines(pages: list[list[Line]]) -> set[str]:
    """Sayfalarin onemli bir kisminda birebir tekrar eden satirlar (ust/alt bilgi adaylari)."""
    if len(pages) < 3:
        return set()
    seen: Counter = Counter()
    for lines in pages:
        seen.update({ln.text for ln in lines})
    limit = max(3, REPEATED_LINE_PAGE_RATIO * len(pages))
    return {text for text, n in seen.items() if n >= limit}


def _repeated_lines(pages: list[list[Line]], frequent: set[str], body: float) -> set[str]:
    """Ust/alt bilgi: sik tekrar eden ve govdeden kucuk puntolu satirlar.

    Govdeyle ayni puntodaki tekrarlar ("Ornek:" gibi) icerik oldugu icin silinmez.
    """
    return {
        ln.text
        for lines in pages
        for ln in lines
        if ln.text in frequent and ln.size < body * SMALL_TEXT_RATIO
    }


def _slide_label_lines(pages: list[list[Line]], body: float) -> set[tuple[int, int]]:
    """Slayt numarasi satirlari: kucuk puntolu "1.5" / "12" bicimli, hep ayni x konumunda duran satirlar.

    "1.5" bicimli numaralar varsa yalnizca onlar kullanilir; boylece kucuk puntolu tablo
    hucrelerindeki "0" / "1" rakamlari slayt numarasi sanilmaz. Numaralar artan sirada olmali.
    """
    candidates = [
        (pi, li, ln)
        for pi, lines in enumerate(pages)
        for li, ln in enumerate(lines)
        if _SLIDE_LABEL.match(ln.text) and ln.size < body * SMALL_TEXT_RATIO
    ]
    dotted = [c for c in candidates if _DOTTED_LABEL.match(c[2].text)]
    if len(dotted) >= 2:
        candidates = dotted
    if len(candidates) < 2:
        return set()
    x_bin = Counter(round(ln.x / 20) for _, _, ln in candidates).most_common(1)[0][0]
    accepted, last = set(), None
    for pi, li, ln in candidates:
        if round(ln.x / 20) != x_bin:
            continue
        key = tuple(int(p) for p in ln.text.split("."))
        if last is None or key > last:
            accepted.add((pi, li))
            last = key
    return accepted


def heading_text_ok(text: str) -> bool:
    """Bicimi baslik olan satirin icerik olarak da baslik olup olmadigi."""
    s = text.strip()
    if not s or len(s) > MAX_HEADING_CHARS or not looks_like_title(s):
        return False
    if s.startswith(BULLETS + ("#",)) or s.endswith((".", ",", ";")):
        return False
    # "8 bit +5", "10000001: Gosterilemiyor" gibi sayisal ornek satirlari
    return not (s[0].isdigit() and not _NUMBERED_TITLE.match(s))


def _mark_headings(lines: list[Line], body: float, page_body: float) -> list[str]:
    big = max(body, page_body) * HEADING_SIZE_RATIO
    bold_min = body * BOLD_HEADING_SIZE_RATIO
    out: list[str] = []
    prev: Optional[Line] = None
    for ln in lines:
        styled = body and (ln.size >= big or (ln.bold and ln.size >= bold_min))
        is_heading = bool(styled) and heading_text_ok(ln.text)
        if (
            is_heading
            and prev is not None
            and abs(prev.size - ln.size) < 0.2
            and len(out[-1]) + len(ln.text) < MAX_HEADING_CHARS
        ):
            out[-1] = f"{out[-1]} {ln.text}"  # iki satira tasan baslik
            continue
        out.append(f"# {ln.text}" if is_heading else ln.text)
        prev = ln if is_heading else None
    return out


def read_pdf_pages(data: bytes) -> list[dict]:
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        raw_pages = [_page_lines(page) for page in doc]

    # Govde puntosu tekrar eden satirlar haric hesaplanir: aksi halde her slaytta tekrar eden
    # uzun bir altbilgi satiri "govde" sanilir
    frequent = _frequent_lines(raw_pages)
    body = _body_size([ln for lines in raw_pages for ln in lines if ln.text not in frequent])
    repeated = _repeated_lines(raw_pages, frequent, body)
    label_lines = _slide_label_lines(raw_pages, body)

    pages: list[dict] = []
    for pi, lines in enumerate(raw_pages):
        # Slayt numarasi slaytin altinda durur: numaraya kadar olan satirlar o slayta aittir
        groups: list[tuple[Optional[str], list[Line]]] = [(None, [])]
        for li, ln in enumerate(lines):
            if (pi, li) in label_lines:
                groups[-1] = (ln.text, groups[-1][1])
                groups.append((None, []))
            elif ln.text not in repeated:
                groups[-1][1].append(ln)
        if not groups[-1][1]:
            groups.pop()
        elif len(groups) > 1 and groups[-1][0] is None:
            label, tail = groups.pop()  # son numaradan sonraki artiklar onceki slayta
            groups[-1][1].extend(tail)

        page_body = _body_size([ln for _, g in groups for ln in g])
        text_parts: list[str] = []
        slides: list[list] = []
        offset = 0
        for label, group in groups:
            block = "\n".join(_mark_headings(group, body, page_body)).strip()
            if not block:
                continue
            if label:
                slides.append([offset, label])
            text_parts.append(block)
            offset += len(block) + 1
        text = "\n".join(text_parts).strip()
        if text:
            page = {"page": pi + 1, "text": text}
            if slides:
                page["slides"] = slides
            pages.append(page)
    return pages
