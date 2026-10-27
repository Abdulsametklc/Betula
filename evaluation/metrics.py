"""Degerlendirme metrikleri: eksik tespiti (P/R/F1) ve bilgi getirme (Hit@k, MRR)."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

_TR_FOLD = str.maketrans("çğıöşüâîû", "cgiosuaiu")
_STOPWORDS = {"ve", "ile", "bir", "bu", "da", "de", "icin", "nedir", "nasil", "konusu", "kavrami"}


def normalize_tr(text: str) -> str:
    """Turkce'ye duyarli kucuk harf + aksan katlama (model ASCII yazsa da eslesir)."""
    s = (text or "").lower().translate(_TR_FOLD)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"^\d+(\.\d+)*[.)]?\s+", "", s)
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", s).split())


def _tokens(text: str) -> set[str]:
    return {t for t in normalize_tr(text).split() if t not in _STOPWORDS and len(t) > 1}


def topic_similarity(a: str, b: str) -> float:
    """0..1; token ortusmesi ile karakter benzerliginin buyugu."""
    ta, tb = _tokens(a), _tokens(b)
    overlap = len(ta & tb) / min(len(ta), len(tb)) if ta and tb else 0.0
    ratio = SequenceMatcher(None, normalize_tr(a), normalize_tr(b)).ratio()
    return max(overlap, ratio)


def match_gaps(predicted: list[str], truth: list[str], threshold: float = 0.6) -> list[tuple[int, int, float]]:
    """Acgozlu bire-bir eslestirme: en benzer ciftler once eslesir."""
    pairs = sorted(
        (
            (topic_similarity(p, t), i, j)
            for i, p in enumerate(predicted)
            for j, t in enumerate(truth)
        ),
        reverse=True,
    )
    used_p, used_t, matches = set(), set(), []
    for score, i, j in pairs:
        if score < threshold:
            break
        if i in used_p or j in used_t:
            continue
        used_p.add(i)
        used_t.add(j)
        matches.append((i, j, score))
    return matches


def gap_scores(predicted: list[str], truth: list[str], threshold: float = 0.6) -> dict:
    matches = match_gaps(predicted, truth, threshold)
    tp = len(matches)
    precision = tp / len(predicted) if predicted else 0.0
    recall = tp / len(truth) if truth else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp,
        "n_pred": len(predicted),
        "n_true": len(truth),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "matches": [{"pred": i, "true": j, "score": round(s, 3)} for i, j, s in matches],
    }


def retrieval_scores(ranked_pages: list[int | None], evidence_pages: list[int], ks=(1, 3, 5)) -> dict:
    """``ranked_pages``: getirilen parcalarin sayfalari (siralı). Kanit sayfasi bulunursa isabet."""
    evidence = set(evidence_pages)
    first = next((r for r, p in enumerate(ranked_pages, start=1) if p in evidence), None)
    out = {f"hit@{k}": float(first is not None and first <= k) for k in ks}
    out["mrr"] = 1.0 / first if first else 0.0
    return out


def mean(rows: list[dict], keys: list[str]) -> dict:
    if not rows:
        return {k: 0.0 for k in keys}
    return {k: sum(r[k] for r in rows) / len(rows) for k in keys}
