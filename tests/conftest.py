"""Ortak test ayarlari.

Testler gercek veritabanina, gercek vektor indeksine veya Groq'a dokunmaz:
- SQLite / uploads / vectorstore gecici bir klasore yonlendirilir
- Embedding modeli deterministik sahte modelle degistirilir (indirme yok, ag yok)
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TMP = Path(tempfile.mkdtemp(prefix="betula-tests-"))
os.environ.update(
    {
        "DATABASE_PATH": str(_TMP / "test.db"),
        "UPLOADS_ROOT": str(_TMP / "uploads"),
        "VECTORSTORE_ROOT": str(_TMP / "vectorstore"),
        "GROQ_API_KEY": "test-key-not-used",
        "JWT_SECRET": "test-secret-test-secret-test-secret-32",
        "DEBUG": "true",
        "SEED_DEFAULT_ADMIN": "false",
    }
)

from backend.config import get_settings  # noqa: E402

get_settings.cache_clear()

from langchain_core.embeddings import DeterministicFakeEmbedding  # noqa: E402

from backend.services import vectorstore  # noqa: E402
from modules.db import init_db  # noqa: E402

vectorstore.set_embeddings(DeterministicFakeEmbedding(size=64))
init_db()


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture
def make_pdf():
    """Verilen sayfa metinlerinden bellekte PDF uretir."""
    import pymupdf as fitz

    def _make(pages: list[str]) -> bytes:
        doc = fitz.open()
        for text in pages:
            page = doc.new_page()
            if text:
                page.insert_text((72, 72), text, fontsize=11)
        data = doc.tobytes()
        doc.close()
        return data

    return _make


@pytest.fixture
def user_and_session():
    """Benzersiz kullanici + calisma oturumu olusturur."""
    import uuid

    from modules.auth import register
    from modules.repo_sessions import create_session

    tag = uuid.uuid4().hex[:8]
    user_id = register(f"u{tag}@example.test", "Parola123!", f"Test {tag}", username=f"u{tag}")
    assert user_id, "kullanici olusturulamadi"
    session_id = create_session(user_id=user_id, title="Test")
    return user_id, session_id
