from backend.services.chunking import SOURCE_EK_BILGI, chunk_id_prefix, chunk_pages, chunk_text
from backend.services.vectorstore import index_chunks, load_vector_db


def _ids(store) -> set[str]:
    return set(store.index_to_docstore_id.values())


def test_search_results_carry_page_metadata():
    chunks = chunk_pages(
        [{"page": 5, "text": "Fotosentez kloroplastta gerceklesir."}],
        document_id=1,
        filename="biyoloji.pdf",
    )
    index_chunks(chunks, user_id=901, session_id=1, id_prefix=chunk_id_prefix(1))

    store = load_vector_db(user_id=901, session_id=1)
    hit = store.similarity_search("Fotosentez kloroplastta gerceklesir.", k=1)[0]
    assert hit.metadata["page"] == 5
    assert hit.metadata["filename"] == "biyoloji.pdf"
    assert hit.metadata["document_id"] == 1


def test_reindex_replaces_only_that_document():
    user, session = 902, 1
    doc_a = chunk_pages([{"page": 1, "text": "A dokumani eski"}], document_id=10)
    doc_b = chunk_pages([{"page": 1, "text": "B dokumani"}], document_id=11)
    index_chunks(doc_a, user_id=user, session_id=session, id_prefix=chunk_id_prefix(10))
    index_chunks(doc_b, user_id=user, session_id=session, id_prefix=chunk_id_prefix(11))

    # A yeniden derlenir: eski A parcalari gider, B kalir
    doc_a_new = chunk_pages([{"page": 2, "text": "A dokumani yeni"}], document_id=10)
    index_chunks(
        doc_a_new, user_id=user, session_id=session, id_prefix=chunk_id_prefix(10), replace=True
    )

    store = load_vector_db(user_id=user, session_id=session)
    contents = {d.page_content for d in store.docstore._dict.values()}
    assert contents == {"A dokumani yeni", "B dokumani"}
    assert _ids(store) == {"doc10:document:0", "doc11:document:0"}


def test_ek_bilgi_is_removed_when_document_is_recompiled():
    user, session = 903, 1
    prefix = chunk_id_prefix(20)
    index_chunks(
        chunk_pages([{"page": 1, "text": "ana metin"}], document_id=20),
        user_id=user, session_id=session, id_prefix=prefix,
    )
    index_chunks(
        chunk_text("sohbetten ek bilgi", document_id=20, source=SOURCE_EK_BILGI),
        user_id=user, session_id=session, id_prefix=f"{prefix}ekabc:",
    )
    assert len(_ids(load_vector_db(user_id=user, session_id=session))) == 2

    index_chunks(
        chunk_pages([{"page": 1, "text": "ana metin v2"}], document_id=20),
        user_id=user, session_id=session, id_prefix=prefix, replace=True,
    )
    assert _ids(load_vector_db(user_id=user, session_id=session)) == {"doc20:document:0"}


def test_sessions_are_isolated():
    index_chunks(
        chunk_text("oturum bir", document_id=30, source="document"),
        user_id=904, session_id=1, id_prefix=chunk_id_prefix(30),
    )
    assert load_vector_db(user_id=904, session_id=2) is None
    assert load_vector_db(user_id=905, session_id=1) is None
