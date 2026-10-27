"""Per-user FAISS vectorstore persistence."""

from __future__ import annotations

import os
import uuid
from typing import Optional

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from backend.config import get_settings
from backend.services.chunking import SOURCE_DOCUMENT, chunk_ids, chunk_text

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

_embeddings: Optional[Embeddings] = None


def get_embeddings() -> Embeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
        )
    return _embeddings


def set_embeddings(embeddings: Optional[Embeddings]) -> None:
    """Embedding modelini degistirir (testler ve degerlendirme deneyleri icin)."""
    global _embeddings
    _embeddings = embeddings


def user_vectorstore_path(user_id: int, session_id: int | None = None) -> str:
    root = get_settings().vectorstore_root
    if session_id:
        return os.path.join(root, f"user_{user_id}", f"session_{session_id}")
    return os.path.join(root, f"user_{user_id}")


def _save(store: FAISS, user_id: int, session_id: int | None) -> None:
    path = user_vectorstore_path(user_id, session_id)
    os.makedirs(path, exist_ok=True)
    store.save_local(path)


def index_chunks(
    chunks: list[Document],
    *,
    user_id: int,
    session_id: int | None = None,
    id_prefix: str,
    replace: bool = False,
) -> Optional[FAISS]:
    """Parcalari oturum indeksine ekler.

    ``replace=True`` ise once ``id_prefix`` ile baslayan eski parcalar silinir; boylece bir
    dokuman yeniden derlendiginde ayni oturumdaki diger dokumanlar korunur.
    """
    store = load_vector_db(user_id=user_id, session_id=session_id)
    if store is not None and replace:
        stale = [i for i in store.index_to_docstore_id.values() if i.startswith(id_prefix)]
        if stale:
            store.delete(stale)

    if not chunks:
        if store is not None:
            _save(store, user_id, session_id)
        return store

    ids = chunk_ids(chunks, prefix=id_prefix)
    if store is None:
        store = FAISS.from_documents(chunks, get_embeddings(), ids=ids)
    else:
        store.add_documents(chunks, ids=ids)
    _save(store, user_id, session_id)
    return store


def create_vector_db(
    text: str, *, user_id: int, persist: bool = True, session_id: int | None = None
) -> FAISS:
    """Eski API: oturum indeksini tek metinden sifirdan kurar (sayfa bilgisi yok)."""
    chunks = chunk_text(text, source=SOURCE_DOCUMENT) or [
        Document(page_content=" ", metadata={"source": SOURCE_DOCUMENT, "chunk_index": 0})
    ]
    ids = chunk_ids(chunks, prefix=f"legacy{uuid.uuid4().hex[:8]}:")
    vectorstore = FAISS.from_documents(chunks, get_embeddings(), ids=ids)
    if persist:
        _save(vectorstore, user_id, session_id)
    return vectorstore


def load_vector_db(*, user_id: int, session_id: int | None = None) -> Optional[FAISS]:
    path = user_vectorstore_path(user_id, session_id)
    index_file = os.path.join(path, "index.faiss")
    if not os.path.exists(index_file):
        # Eski yol (oturumsuz) yedek
        if session_id:
            legacy = user_vectorstore_path(user_id)
            if os.path.exists(os.path.join(legacy, "index.faiss")):
                return FAISS.load_local(
                    legacy, get_embeddings(), allow_dangerous_deserialization=True
                )
        return None
    return FAISS.load_local(
        path,
        get_embeddings(),
        allow_dangerous_deserialization=True,
    )


def add_to_vector_db(
    text: str, *, user_id: int, existing: Optional[FAISS] = None, session_id: int | None = None
) -> FAISS:
    """Eski API: metni sayfa bilgisi olmadan indekse ekler."""
    chunks = chunk_text(text, source=SOURCE_DOCUMENT)
    store = existing or load_vector_db(user_id=user_id, session_id=session_id)
    if store is not None and not chunks:
        return store
    if store is None:
        return create_vector_db(text, user_id=user_id, persist=True, session_id=session_id)

    store.add_documents(chunks, ids=chunk_ids(chunks, prefix=f"legacy{uuid.uuid4().hex[:8]}:"))
    _save(store, user_id, session_id)
    return store
