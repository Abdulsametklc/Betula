"""Per-user FAISS vectorstore persistence."""

from __future__ import annotations

import os
from typing import Optional

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.config import get_settings

_embeddings: Optional[HuggingFaceEmbeddings] = None


def get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            model_kwargs={"device": "cpu"},
        )
    return _embeddings


def user_vectorstore_path(user_id: int, session_id: int | None = None) -> str:
    root = get_settings().vectorstore_root
    if session_id:
        return os.path.join(root, f"user_{user_id}", f"session_{session_id}")
    return os.path.join(root, f"user_{user_id}")


def create_vector_db(
    text: str, *, user_id: int, persist: bool = True, session_id: int | None = None
) -> FAISS:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=750,
        chunk_overlap=150,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_text(text)
    if not chunks:
        chunks = [text or " "]

    vectorstore = FAISS.from_texts(texts=chunks, embedding=get_embeddings())
    if persist:
        path = user_vectorstore_path(user_id, session_id)
        os.makedirs(path, exist_ok=True)
        vectorstore.save_local(path)
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
    splitter = RecursiveCharacterTextSplitter(chunk_size=750, chunk_overlap=150)
    chunks = splitter.split_text(text)
    if not chunks:
        chunks = [text or " "]

    store = existing or load_vector_db(user_id=user_id, session_id=session_id)
    if store is None:
        return create_vector_db(text, user_id=user_id, persist=True, session_id=session_id)

    store.add_texts(chunks)
    path = user_vectorstore_path(user_id, session_id)
    os.makedirs(path, exist_ok=True)
    store.save_local(path)
    return store
