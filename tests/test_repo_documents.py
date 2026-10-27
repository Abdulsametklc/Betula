from modules.repo_documents import create_document, get_document, get_document_pages


def test_pages_round_trip(user_and_session):
    user_id, session_id = user_and_session
    pages = [{"page": 1, "text": "giris"}, {"page": 3, "text": "sonuc"}]
    doc_id = create_document(
        "ders.pdf", "giris\nsonuc", "pdf", user_id=user_id, session_id=session_id, pages=pages
    )

    doc = get_document(doc_id, user_id=user_id)
    assert get_document_pages(doc) == pages


def test_legacy_document_without_pages_falls_back_to_content(user_and_session):
    user_id, session_id = user_and_session
    doc_id = create_document("eski.pdf", "tum metin", "pdf", user_id=user_id, session_id=session_id)

    doc = get_document(doc_id, user_id=user_id)
    assert get_document_pages(doc) == [{"page": None, "text": "tum metin"}]


def test_documents_are_user_isolated(user_and_session):
    user_id, session_id = user_and_session
    doc_id = create_document("x.pdf", "gizli", "pdf", user_id=user_id, session_id=session_id)
    assert get_document(doc_id, user_id=user_id + 10_000) is None
