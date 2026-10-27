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


def inject_gaps(
    pages: list[dict],
    *,
    k: int,
    seed: int,
    mode: str = "body",
    min_body_chars: int = 150,
) -> tuple[list[dict], list[InjectedGap]]:
    """``k`` bolumu siler; (eksikli sayfalar, ground-truth eksik listesi) dondurur."""
    if mode not in MODES:
        raise ValueError(f"mode {MODES} olmali")
    sections = split_sections(pages)
    eligible = [i for i, s in enumerate(sections) if len(s.body) >= min_body_chars]
    if len(eligible) < k:
        raise ValueError(f"Yeterli bolum yok: {len(eligible)} uygun bolum, {k} istendi")

    chosen = sorted(random.Random(seed).sample(eligible, k))
    new_pages = [dict(p) for p in pages]
    gaps: list[InjectedGap] = []
    for n, idx in enumerate(chosen):
        sec = sections[idx]
        page = next(p for p in new_pages if p["page"] == sec.page)
        removed = sec.body if mode == "body" else f"{sec.heading}\n{sec.body}"
        page["text"] = page["text"].replace(removed, "", 1)
        page["text"] = re.sub(r"\n{3,}", "\n\n", page["text"]).strip()
        gaps.append(InjectedGap(f"g{n + 1}", sec.title, sec.page, removed))
    return new_pages, gaps


def gaps_to_dicts(gaps: list[InjectedGap]) -> list[dict]:
    return [asdict(g) for g in gaps]
