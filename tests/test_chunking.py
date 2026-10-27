from backend.services.chunking import (
    CHUNK_SIZE,
    SOURCE_COMPILED_NOTE,
    SOURCE_DOCUMENT,
    chunk_id_prefix,
    chunk_ids,
    chunk_pages,
    chunk_text,
    format_citation,
    format_context,
    format_source,
)


def _long(word: str, n: int = 400) -> str:
    return " ".join(f"{word}{i}" for i in range(n))


def test_chunks_never_cross_pages():
    pages = [{"page": 1, "text": _long("alfa")}, {"page": 2, "text": _long("beta")}]
    chunks = chunk_pages(pages, document_id=7, filename="ders.pdf")

    assert len(chunks) > 2
    for c in chunks:
        assert len(c.page_content) <= CHUNK_SIZE
        word = "alfa" if c.metadata["page"] == 1 else "beta"
        other = "beta" if word == "alfa" else "alfa"
        assert word in c.page_content and other not in c.page_content


def test_metadata_fields_and_offsets():
    text = _long("gama")
    chunks = chunk_pages([{"page": 4, "text": text}], document_id=3, filename="a.pdf")

    for i, c in enumerate(chunks):
        meta = c.metadata
        assert meta["source"] == SOURCE_DOCUMENT
        assert meta["document_id"] == 3
        assert meta["filename"] == "a.pdf"
        assert meta["page"] == 4
        assert meta["chunk_index"] == i
        # start_index metindeki gercek konumu gosterir
        start = meta["start_index"]
        assert text[start : start + len(c.page_content)] == c.page_content


def test_chunk_index_is_global_across_pages():
    pages = [{"page": 1, "text": _long("a", 200)}, {"page": 2, "text": _long("b", 200)}]
    chunks = chunk_pages(pages, document_id=1)
    assert [c.metadata["chunk_index"] for c in chunks] == list(range(len(chunks)))


def test_empty_pages_are_skipped():
    assert chunk_pages([{"page": 1, "text": "   "}, {"page": 2, "text": ""}]) == []


def test_ids_are_deterministic_and_prefixed():
    chunks = chunk_text("kisa not", document_id=9, source=SOURCE_COMPILED_NOTE)
    ids = chunk_ids(chunks, prefix=chunk_id_prefix(9))
    assert ids == ["doc9:compiled_note:0"]
    assert chunk_id_prefix(None) == "session:"


def test_citation_formats():
    page_chunk = chunk_pages([{"page": 12, "text": "Newton yasalari"}], filename="fizik.pdf")[0]
    note_chunk = chunk_text("Sentez", source=SOURCE_COMPILED_NOTE)[0]

    assert format_citation(page_chunk) == "fizik.pdf · s. 12"
    assert format_citation(note_chunk) == "Master Sentez"
    assert format_source(page_chunk).startswith("[fizik.pdf · s. 12] Newton")
    assert format_context([page_chunk]) == "[Kaynak: fizik.pdf · s. 12]\nNewton yasalari"
