"""Sentetik eksik enjeksiyonu: eksiksiz bir nottan bilinen bolumleri silerek
cevabi bilinen (ground-truth) eksikler uretir.

Iki mod:
- ``body`` (varsayilan): baslik kalir, govde silinir -> "adi gecen ama anlatilmayan konu".
  Gercek ogrenci notlarindaki yarim birakilmis bolumlere en yakin senaryo.
- ``full``: baslik + govde silinir -> konu tamamen kaybolur (daha zor senaryo).

Ayni (dokuman, seed, k, mod) her zaman ayni ciktiyi verir.
"""

from __future__ import annotations

import random
import re
from dataclasses import asdict, dataclass

from backend.services.sections import clean_heading, is_heading

MODES = ("body", "full")


@dataclass
class Section:
    page: int | None
    heading: str
    title: str
    body: str


def split_sections(pages: list[dict]) -> list[Section]:
    """Her sayfayi baslik + govde bolumlerine ayirir (bolum sayfa icinde kalir)."""
    sections: list[Section] = []
    for page in pages:
        heading, body = None, []
        for line in page["text"].splitlines():
            if is_heading(line):
                if heading is not None:
                    sections.append(Section(page["page"], heading, clean_heading(heading), "\n".join(body).strip()))
                heading, body = line, []
            elif heading is not None:
                body.append(line)
        if heading is not None:
            sections.append(Section(page["page"], heading, clean_heading(heading), "\n".join(body).strip()))
    return sections


@dataclass
class InjectedGap:
    gap_id: str
    title: str
    page: int | None
    removed_text: str


# Ayni baslik bundan fazla bolumde geciyorsa (or. her slaytta tekrar eden ders basligi)
# o baslik bir "konu" degildir; eksik olarak secilmez.
MAX_SECTIONS_PER_TOPIC = 3


def topics(sections: list[Section]) -> dict[str, list[Section]]:
    """Bolumleri basliga gore konulara toplar ("X" ve "X (devami)" ayni konudur)."""
    grouped: dict[str, list[Section]] = {}
    for sec in sections:
        grouped.setdefault(sec.title.casefold(), []).append(sec)
    return grouped


def inject_gaps(
    pages: list[dict],
    *,
    k: int,
    seed: int,
    mode: str = "body",
    min_body_chars: int = 150,
) -> tuple[list[dict], list[InjectedGap]]:
    """``k`` konuyu siler; (eksikli sayfalar, ground-truth eksik listesi) dondurur.

    Bir konu birden fazla slayta yayiliyorsa ("... (devami)") hepsi birlikte silinir.
    """
    if mode not in MODES:
        raise ValueError(f"mode {MODES} olmali")
    grouped = topics(split_sections(pages))
    eligible = [
        key
        for key, secs in grouped.items()
        if len(secs) <= MAX_SECTIONS_PER_TOPIC and sum(len(s.body) for s in secs) >= min_body_chars
    ]
    if len(eligible) < k:
        raise ValueError(f"Yeterli bolum yok: {len(eligible)} uygun bolum, {k} istendi")

    chosen = sorted(random.Random(seed).sample(eligible, k), key=eligible.index)
    # Silinen metin konumlari degistirdigi icin slayt ofsetleri eksikli kopyada tutulmaz
    new_pages = [{key: v for key, v in p.items() if key != "slides"} for p in pages]
    gaps: list[InjectedGap] = []
    for n, key in enumerate(chosen):
        secs = grouped[key]
        removed_parts = []
        for sec in secs:
            page = next(p for p in new_pages if p["page"] == sec.page)
            removed = sec.body if mode == "body" else f"{sec.heading}\n{sec.body}"
            if not removed.strip():
                continue
            page["text"] = page["text"].replace(removed, "", 1)
            page["text"] = re.sub(r"\n{3,}", "\n\n", page["text"]).strip()
            removed_parts.append(removed)
        gaps.append(InjectedGap(f"g{n + 1}", secs[0].title, secs[0].page, "\n\n".join(removed_parts)))
    return new_pages, gaps


def gaps_to_dicts(gaps: list[InjectedGap]) -> list[dict]:
    return [asdict(g) for g in gaps]
