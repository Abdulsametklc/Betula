"""Metindeki bolum basliklarini tespit eder (parcalama ve degerlendirme ortak kullanir).

Baslik sayilan satirlar:
- Markdown basligi: ``# Ivme`` (PDF okuyucu, buyuk punto satirlari bu bicime cevirir)
- Numarali baslik: ``2.1 Ortalama Hiz`` (nokta / virgulle bitmeyen)
- Tamami BUYUK HARF kisa satir: ``SERBEST DUSME``
"""

from __future__ import annotations

import re
from typing import Iterator, Optional

MAX_HEADING_CHARS = 90

_NUMBERED = re.compile(r"^\d+(\.\d+)*[.)]?\s+\S")
_MARKDOWN = re.compile(r"^#{1,6}\s+\S")


def is_heading(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > MAX_HEADING_CHARS:
        return False
    if _MARKDOWN.match(s):
        return True
    if _NUMBERED.match(s) and not s.endswith((".", ",", ";", ":")):
        return True
    letters = [c for c in s if c.isalpha()]
    return len(letters) >= 4 and all(c.isupper() for c in letters)


def clean_heading(line: str) -> str:
    s = line.strip().lstrip("#").strip()
    return re.sub(r"^\d+(\.\d+)*[.)]?\s+", "", s).strip()


def iter_blocks(text: str, current: Optional[str] = None) -> Iterator[tuple[int, int, Optional[str]]]:
    """Metni basliklardan boler: (baslangic, bitis, bolum basligi).

    Ilk basliktan onceki kisim ``current`` bolumune (onceki sayfadan devam eden) aittir.
    """
    start, section, pos = 0, current, 0
    for line in text.splitlines(keepends=True):
        if is_heading(line) and pos > start:
            yield start, pos, section
            start = pos
        if is_heading(line):
            section = clean_heading(line)
        pos += len(line)
    if pos > start:
        yield start, pos, section
