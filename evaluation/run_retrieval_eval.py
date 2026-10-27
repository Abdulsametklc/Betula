"""Bilgi getirme deneyi: dogru kanit sayfasi ilk k parcada mi?

    python -m evaluation.run_retrieval_eval --k 5
    python -m evaluation.run_retrieval_eval --fake-embeddings   # hizli duman testi (anlamsiz skor)

Her korpus dokumani bellekte ayri bir FAISS indeksine, uygulamadaki ayni parcalama ile
(``chunk_pages``) yuklenir; ``evaluation/data/qa/<doc_id>.jsonl`` sorulari sorulur.
Sonuc: evaluation/results/retrieval_eval_<zaman>.json
"""

from __future__ import annotations

import argparse
import json

from langchain_community.vectorstores import FAISS

from backend.services.chunking import CHUNK_OVERLAP, CHUNK_SIZE, chunk_pages
from evaluation.corpus import iter_corpus, load_qa
from evaluation.metrics import mean, retrieval_scores
from evaluation.runinfo import write_result

KS = (1, 3, 5)


def run(embeddings, *, k: int, only: list[str] | None = None) -> tuple[dict, list[dict]]:
    items = []
    for doc in iter_corpus(only):
        questions = load_qa(doc.doc_id)
        chunks = chunk_pages(doc.pages, filename=doc.filename)
        if not questions or not chunks:
            continue
        store = FAISS.from_documents(chunks, embeddings)
        for q in questions:
            hits = store.similarity_search(q["question"], k=k)
            ranked = [h.metadata.get("page") for h in hits]
            scores = retrieval_scores(ranked, q["evidence_pages"], ks=[x for x in KS if x <= k])
            items.append({"doc_id": doc.doc_id, "question": q["question"], "evidence_pages": q["evidence_pages"], "ranked_pages": ranked, **scores})
    keys = [f"hit@{x}" for x in KS if x <= k] + ["mrr"]
    summary = {**mean(items, keys), "n_questions": len(items)}
    return summary, items


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--fake-embeddings", action="store_true")
    args = ap.parse_args()

    if args.fake_embeddings:
        from langchain_core.embeddings import DeterministicFakeEmbedding

        embeddings, emb_name = DeterministicFakeEmbedding(size=64), "fake"
    else:
        from backend.services.vectorstore import EMBEDDING_MODEL, get_embeddings

        embeddings, emb_name = get_embeddings(), EMBEDDING_MODEL

    summary, items = run(embeddings, k=args.k, only=args.only)
    if not items:
        raise SystemExit("Soru yok. evaluation/data/qa/<doc_id>.jsonl ekleyin.")
    config = {"embedding": emb_name, "k": args.k, "chunk_size": CHUNK_SIZE, "chunk_overlap": CHUNK_OVERLAP}
    path = write_result("retrieval_eval", config, summary, items)
    print(json.dumps(summary, indent=2))
    print(f"Sonuc: {path}")


if __name__ == "__main__":
    main()
