"""Kaynak bilgisini (dosya, sayfa, konum) koruyan parcalama.

Her parca bir LangChain ``Document``'tir; ``metadata`` alanlari:

- ``source``      : "document" | "compiled_note" | "ek_bilgi"
- ``document_id`` : kaynak dokuman id (yoksa None)
- ``filename``    : kaynak dosya adi (yoksa None)
- ``page``        : 1-tabanli sayfa no (sayfasiz kaynaklarda None)
- ``slide``       : slayt numarasi, or. "1.5" (slayt PDF'i degilse None)
- ``section``     : parcanin ait oldugu bolum basligi (tespit edilemezse None)
- ``chunk_index`` : kaynak icindeki sira (0'dan)
- ``start_index`` : parcanin sayfa/metin icindeki karakter konumu

Parcalar sayfa ve bolum sinirini asmaz; boylece her cevap tek bir sayfaya ve bolume
atfedilebilir.
"""

from __future__ import annotations

from typing import Iterable, Optional

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.services.sections import iter_blocks

CHUNK_SIZE = 750
CHUNK_OVERLAP = 150

SOURCE_DOCUMENT = "document"
SOURCE_COMPILED_NOTE = "compiled_note"
SOURCE_EK_BILGI = "ek_bilgi"


def _splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        add_start_index=True,
    )


def chunk_id_prefix(document_id: Optional[int]) -> str:
    """Bir dokumana ait tum parcalarin ortak id oneki (yeniden indekslemede silmek icin)."""
    return f"doc{document_id}:" if document_id is not None else "session:"


def chunk_pages(
    pages: Iterable[dict],
    *,
    document_id: Optional[int] = None,
    filename: Optional[str] = None,
    source: str = SOURCE_DOCUMENT,
) -> list[Document]:
    """Sayfa listesini ({"page", "text", "slides"?}) metadata'li parcalara boler.

    Parcalar bolum basliklarinda ve slayt sinirlarinda da kesilir; bir sayfa basliksiz
    basliyorsa onceki sayfanin bolumu devam ediyor kabul edilir.
    """
    splitter = _splitter()
    chunks: list[Document] = []
    section = None
    for page in pages:
        text = (page.get("text") or "").strip()
        if not text:
            continue
        slides = sorted((int(o), str(label)) for o, label in page.get("slides") or [])
        for start, end, section in iter_blocks(text, current=section):
            for s, e in _split_at(start, end, [o for o, _ in slides]):
                block = text[s:e]
                if not block.strip():
                    continue
                slide = next((label for o, label in reversed(slides) if o <= s), None)
                for piece in splitter.create_documents([block]):
                    chunks.append(
                        Document(
                            page_content=piece.page_content,
                            metadata={
                                "source": source,
                                "document_id": document_id,
                                "filename": filename,
                                "page": page.get("page"),
                                "slide": slide,
                                "section": section,
                                "chunk_index": len(chunks),
                                "start_index": s + piece.metadata.get("start_index", 0),
                            },
                        )
                    )
    return chunks


def _split_at(start: int, end: int, cuts: list[int]) -> list[tuple[int, int]]:
    """[start, end) araligini icindeki kesim noktalarindan boler."""
    points = [start] + [c for c in cuts if start < c < end] + [end]
    return list(zip(points, points[1:]))


def chunk_text(
    text: str,
    *,
    document_id: Optional[int] = None,
    filename: Optional[str] = None,
    source: str,
) -> list[Document]:
    """Sayfasiz metni (sentez notu, ek bilgi) parcalar."""
    return chunk_pages(
        [{"page": None, "text": text}],
        document_id=document_id,
        filename=filename,
        source=source,
    )


def chunk_ids(chunks: list[Document], *, prefix: str) -> list[str]:
    """Deterministik parca id'leri: ``<prefix><source>:<chunk_index>``."""
    return [f"{prefix}{c.metadata['source']}:{c.metadata['chunk_index']}" for c in chunks]


def format_citation(doc: Document) -> str:
    """Kullaniciya gosterilecek kisa kaynak etiketi, or. ``ders.pdf · s. 3 / slayt 1.5 · BCD``."""
    meta = doc.metadata or {}
    source = meta.get("source")
    if source == SOURCE_COMPILED_NOTE:
        label = "Master Sentez"
    elif source == SOURCE_EK_BILGI:
        label = "Ek bilgi"
    else:
        label = meta.get("filename") or "Dokuman"
    if meta.get("page") is not None:
        label += f" · s. {meta['page']}"
        if meta.get("slide") and str(meta["slide"]) != str(meta["page"]):
            label += f" / slayt {meta['slide']}"
    if meta.get("section"):
        section = meta["section"]
        label += f" · {section[:40] + '…' if len(section) > 40 else section}"
    return label


def format_source(doc: Document, snippet_len: int = 160) -> str:
    """Sohbet yanitindaki ``sources`` listesi icin: etiket + kisa alinti."""
    snippet = " ".join(doc.page_content.split())[:snippet_len]
    return f"[{format_citation(doc)}] {snippet}"


def format_context(docs: Iterable[Document]) -> str:
    """LLM baglami: her parcanin basina kaynak etiketi koyar, boylece model atif yapabilir."""
    return "\n\n".join(f"[Kaynak: {format_citation(d)}]\n{d.page_content}" for d in docs)
