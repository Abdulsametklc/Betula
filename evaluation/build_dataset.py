"""Korpustan eksik enjekte edilmis degerlendirme ornekleri uretir.

    python -m evaluation.build_dataset --k 3 --seeds 1 2 3 --mode body

Cikti: evaluation/data/generated/<doc_id>__<mode>_k<k>_s<seed>.json
"""

from __future__ import annotations

import argparse
import json

from evaluation.corpus import GENERATED_DIR, iter_corpus
from evaluation.gap_injection import MODES, gaps_to_dicts, inject_gaps


def build(k: int, seeds: list[int], mode: str, only: list[str] | None = None) -> list[str]:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for doc in iter_corpus(only):
        for seed in seeds:
            try:
                pages, gaps = inject_gaps(doc.pages, k=k, seed=seed, mode=mode)
            except ValueError as e:
                print(f"[atlandi] {doc.doc_id} seed={seed}: {e}")
                continue
            sample_id = f"{doc.doc_id}__{mode}_k{k}_s{seed}"
            payload = {
                "sample_id": sample_id,
                "doc_id": doc.doc_id,
                "filename": doc.filename,
                "mode": mode,
                "k": k,
                "seed": seed,
                "pages": pages,
                "gaps": gaps_to_dicts(gaps),
            }
            path = GENERATED_DIR / f"{sample_id}.json"
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            written.append(str(path))
            print(f"[ok] {sample_id}: {[g.title for g in gaps]}")
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--k", type=int, default=3, help="dokuman basina silinecek bolum sayisi")
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--mode", choices=MODES, default="body")
    ap.add_argument("--only", nargs="*", help="yalnizca bu doc_id'ler")
    args = ap.parse_args()
    build(args.k, args.seeds, args.mode, args.only)


if __name__ == "__main__":
    main()
