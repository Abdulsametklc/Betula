"""Metindeki bolum basliklarini tespit eder (parcalama ve degerlendirme ortak kullanir).

Baslik sayilan satirlar:
- Markdown basligi: ``# Ivme`` (PDF okuyucu, baslik bicimli satirlari bu bicime cevirir)
- Numarali baslik: ``2.1 Ortalama Hiz`` (numaradan sonra buyuk harf; nokta / virgulle bitmeyen)
- Tamami BUYUK HARF kisa satir: ``SERBEST DUSME``
"""

from __future__ import annotations

import re
from typing import Iterator, Optional

MAX_HEADING_CHARS = 90

# Kalin yazilsa da bolum basligi olmayan etiketler ("Ornek:", "Cozum:" ...)
GENERIC_LABELS = {
    "örnek", "örnekler", "örnek tümdevre", "not", "notlar", "çözüm", "kanıt", "ispat", "yöntem",
    "sonuç", "hatırlatma", "uyarı", "dikkat", "tanım", "soru", "cevap", "alıştırma", "adım",
    "example", "examples", "note", "solution", "proof", "remark", "exercise", "step",
}

_NUMBERED = re.compile(r"^\d+(\.\d+)*[.)]?\s+[A-ZÇĞİÖŞÜ]")
_MARKDOWN = re.compile(r"^#{1,6}\s+\S")
_CONTINUED = re.compile(r"\s*\((devamı|devam|continued|cont\.?)\)\s*$", re.IGNORECASE)
_WORD = re.compile(r"[^\W\d_]{4,}")
# Formul / denklem satirlarinda gecen isaretler ("F = A'B + C", "X=0 →S=A+B")
_FORMULA_CHARS = set("=+•⋅·→←≤≥<>∪∩ΠΣ∑∏√≈≠")


_SENTENCE_BREAK = re.compile(r"[.!?]\s+[A-ZÇĞİÖŞÜ0-9]")
_TR_FOLD = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def _fold(text: str) -> str:
    """Turkce karakterleri sadelestirip kucuk harfe cevirir ("Örnek" == "Ornek")."""
    return text.translate(_TR_FOLD).lower()


_FOLDED_LABELS = {_fold(label) for label in GENERIC_LABELS}
_LEADING_NUMBER = re.compile(r"^\d+(\.\d+)*[.)]?\s*")


def looks_like_title(text: str) -> bool:
    """Satir iceriginin baslik gibi olup olmadigi.

    Elenenler: formul satirlari, harf orani dusuk satirlar, kucuk harfle baslayan parcalar
    ("veya"), birden fazla cumle ya da satira bolunmus cumle, "Ornek:" gibi etiketler.
    """
    s = text.strip().lstrip("#").strip()
    if not _WORD.search(s) or any(ch in _FORMULA_CHARS for ch in s):
        return False
    visible = [c for c in s if not c.isspace()]
    letters = sum(c.isalpha() for c in visible)
    if not visible or letters / len(visible) < 0.6:
        return False
    body = _LEADING_NUMBER.sub("", s)
    first_letter = next((c for c in body if c.isalpha()), "")
    if not first_letter.isupper():
        return False
    if _SENTENCE_BREAK.search(body) or s.count("(") != s.count(")"):
        return False
    return _fold(body.split(":", 1)[0].strip()) not in _FOLDED_LABELS


def is_heading(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > MAX_HEADING_CHARS + 2:
        return False
    if _MARKDOWN.match(s):
        return True
    if s.endswith((".", ",", ";", ":")) or not looks_like_title(s):
        return False
    if _NUMBERED.match(s):
        return True
    # BUYUK HARF baslik: en az iki gercek kelime ("SERBEST DUSME"; "A'BCD", "CLEAR" degil)
    letters = [c for c in s if c.isalpha()]
    words = [w for w in s.split() if sum(c.isalpha() for c in w) >= 3]
    return len(words) >= 2 and all(c.isupper() for c in letters)


def clean_heading(line: str) -> str:
    """``## 3.2) Serbest Dusme (devami):`` -> ``Serbest Dusme``"""
    s = line.strip().lstrip("#").strip()
    s = re.sub(r"^\d+(\.\d+)*[.)]?\s+", "", s).strip()
    s = s.rstrip(":").strip()
    return _CONTINUED.sub("", s).rstrip(":").strip()


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
