import pytest
from fastapi.testclient import TestClient

from backend.auth.jwt import create_access_token
from backend.main import app
from modules.repo_documents import get_document, get_document_pages


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_documents_require_auth(client):
    assert client.get("/documents").status_code == 401


def test_upload_stores_pages(client, make_pdf, user_and_session):
    user_id, session_id = user_and_session
    headers = {
        "Authorization": f"Bearer {create_access_token(user_id, 'x@example.test')}",
        "X-Session-Id": str(session_id),
    }
    pdf = make_pdf(["ilk sayfa", "ikinci sayfa"])

    res = client.post(
        "/documents/upload?auto_compile=false",
        headers=headers,
        files={"file": ("ders.pdf", pdf, "application/pdf")},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["job"] is None

    doc = get_document(body["document_id"], user_id=user_id)
    assert [p["page"] for p in get_document_pages(doc)] == [1, 2]


def test_upload_rejects_doc(client, user_and_session):
    user_id, session_id = user_and_session
    headers = {
        "Authorization": f"Bearer {create_access_token(user_id, 'x@example.test')}",
        "X-Session-Id": str(session_id),
    }
    res = client.post(
        "/documents/upload?auto_compile=false",
        headers=headers,
        files={"file": ("eski.doc", b"\xd0\xcf\x11\xe0", "application/msword")},
    )
    assert res.status_code == 400
