"""Eksik tespiti deneyi: uretilmis orneklerde pipeline'in eksik analizini olcer.

    python -m evaluation.run_gap_eval                      # Groq ile (GROQ_API_KEY gerekir)
    python -m evaluation.run_gap_eval --predictions p.json # hazir tahminlerle (baseline / baska sistem)

``--predictions`` dosyasi: {"<sample_id>": ["tahmin edilen konu", ...], ...}
Sonuc: evaluation/results/gap_eval_<zaman>.json
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from backend.llm.telemetry import summarize_usage, track_llm_usage
from evaluation.corpus import GENERATED_DIR
from evaluation.metrics import gap_scores, mean
from evaluation.runinfo import sha256, write_result


def load_samples(pattern: str) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(GENERATED_DIR.glob(pattern))]


def pipeline_predictor(max_gaps: int):
    from backend.agents.research_graph import analyze_gaps
    from backend.services.documents import pages_to_text

    def predict(sample: dict) -> list[str]:
        result = analyze_gaps(pages_to_text(sample["pages"]), max_gaps=max_gaps)
        return [str(g.get("topic") or "") for g in result["gaps"] if isinstance(g, dict)]

    return predict


def run(samples: list[dict], predict, *, threshold: float) -> tuple[dict, list[dict]]:
    items = []
    for sample in samples:
        truth = [g["title"] for g in sample["gaps"]]
        started = time.time()
        with track_llm_usage() as calls:
            try:
                predicted, error = predict(sample), None
            except Exception as e:  # deney devam etsin, hata kayda gecsin
                predicted, error = [], str(e)
        scores = gap_scores(predicted, truth, threshold)
        items.append(
            {
                "sample_id": sample["sample_id"],
                "truth": truth,
                "predicted": predicted,
                "latency_s": round(time.time() - started, 2),
                "error": error,
                **summarize_usage(calls),
                **scores,
            }
        )
        print(f"{sample['sample_id']}: P={scores['precision']:.2f} R={scores['recall']:.2f} F1={scores['f1']:.2f}")

    summary = mean(items, ["precision", "recall", "f1", "latency_s"])
    # Mikro ortalama: tum orneklerin TP/tahmin/gercek toplamindan
    tp = sum(i["tp"] for i in items)
    n_pred = sum(i["n_pred"] for i in items)
    n_true = sum(i["n_true"] for i in items)
    p = tp / n_pred if n_pred else 0.0
    r = tp / n_true if n_true else 0.0
    summary.update(
        {
            "n_samples": len(items),
            "n_errors": sum(1 for i in items if i["error"]),
            "micro_precision": p,
            "micro_recall": r,
            "micro_f1": 2 * p * r / (p + r) if p + r else 0.0,
            "prompt_tokens": sum(i["prompt_tokens"] for i in items),
            "completion_tokens": sum(i["completion_tokens"] for i in items),
        }
    )
    return summary, items


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pattern", default="*.json", help="generated/ icinde ornek secimi (glob)")
    ap.add_argument("--predictions", type=Path, help="hazir tahmin dosyasi (LLM cagrisi yapilmaz)")
    ap.add_argument("--max-gaps", type=int, default=5)
    ap.add_argument("--threshold", type=float, default=0.6, help="konu eslesme esigi")
    ap.add_argument("--label", default="pipeline", help="sonuc dosyasinda sistem adi")
    args = ap.parse_args()

    samples = load_samples(args.pattern)
    if not samples:
        raise SystemExit("Ornek yok. Once: python -m evaluation.build_dataset")

    config = {"system": args.label, "threshold": args.threshold, "pattern": args.pattern}
    if args.predictions:
        table = json.loads(args.predictions.read_text(encoding="utf-8"))
        predict = lambda s: table.get(s["sample_id"], [])  # noqa: E731
        config["predictions_file"] = str(args.predictions)
    else:
        from backend.agents.research_graph import GAP_PROMPT
        from backend.config import get_settings

        predict = pipeline_predictor(args.max_gaps)
        config.update(
            {"model": get_settings().groq_model, "max_gaps": args.max_gaps, "gap_prompt_sha": sha256(GAP_PROMPT)}
        )

    summary, items = run(samples, predict, threshold=args.threshold)
    path = write_result("gap_eval", config, summary, items)
    print(json.dumps(summary, indent=2))
    print(f"Sonuc: {path}")


if __name__ == "__main__":
    main()
