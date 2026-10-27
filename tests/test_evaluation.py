import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding

from evaluation import run_gap_eval, run_retrieval_eval
from evaluation.corpus import iter_corpus, parse_marked_text
from evaluation.gap_injection import inject_gaps, is_heading, split_sections
from evaluation.metrics import gap_scores, normalize_tr, retrieval_scores, topic_similarity

SAMPLE = "ornek-fizik-hareket"


@pytest.fixture
def sample_doc():
    return iter_corpus([SAMPLE])[0]


def test_page_markers():
    pages = parse_marked_text("<!-- page: 2 -->\nA\n<!-- page: 5 -->\nB")
    assert pages == [{"page": 2, "text": "A"}, {"page": 5, "text": "B"}]
    assert parse_marked_text("isaretsiz") == [{"page": None, "text": "isaretsiz"}]


def test_heading_detection():
    assert is_heading("# 3. İvme")
    assert is_heading("2.1 Ortalama Hız")
    assert is_heading("SERBEST DÜŞME")
    assert not is_heading("Bu bir cümledir.")
    assert not is_heading("1. adımda hız artar.")


def test_sample_corpus_loads(sample_doc):
    assert [p["page"] for p in sample_doc.pages] == [1, 2, 3]
    titles = [s.title for s in split_sections(sample_doc.pages)]
    assert titles[0] == "Konum, Yer Değiştirme ve Yol" and len(titles) == 6


def test_injection_is_deterministic_and_removes_body(sample_doc):
    pages_a, gaps_a = inject_gaps(sample_doc.pages, k=2, seed=7)
    pages_b, gaps_b = inject_gaps(sample_doc.pages, k=2, seed=7)
    assert pages_a == pages_b and gaps_a == gaps_b

    full_text = "\n".join(p["text"] for p in pages_a)
    for gap in gaps_a:
        assert gap.title in full_text  # body modu: baslik kalir
        assert gap.removed_text not in full_text


def test_full_mode_removes_heading(sample_doc):
    pages, gaps = inject_gaps(sample_doc.pages, k=1, seed=3, mode="full")
    assert gaps[0].title not in "\n".join(p["text"] for p in pages)


def test_injection_rejects_too_many_gaps(sample_doc):
    with pytest.raises(ValueError):
        inject_gaps(sample_doc.pages, k=50, seed=1)


def test_turkish_normalization_and_similarity():
    assert normalize_tr("2. Serbest DÜŞME!") == "serbest dusme"
    assert topic_similarity("Serbest düşme hareketi", "Serbest Dusme") >= 0.6
    assert topic_similarity("İvme", "Termodinamik yasaları") < 0.6


def test_gap_scores_one_to_one():
    scores = gap_scores(["İvme kavramı", "ivme", "Optik"], ["İvme", "Serbest Düşme"])
    assert scores["tp"] == 1  # ayni gercek eksik iki kez sayilmaz
    assert scores["precision"] == pytest.approx(1 / 3)
    assert scores["recall"] == pytest.approx(1 / 2)


def test_retrieval_scores():
    s = retrieval_scores([3, 1, 2], [1], ks=[1, 3])
    assert s == {"hit@1": 0.0, "hit@3": 1.0, "mrr": 0.5}
    assert retrieval_scores([2, 2], [1], ks=[1])["mrr"] == 0.0


def test_gap_eval_with_oracle_predictions(sample_doc):
    pages, gaps = inject_gaps(sample_doc.pages, k=2, seed=1)
    sample = {"sample_id": "s1", "pages": pages, "gaps": [{"title": g.title} for g in gaps]}
    summary, items = run_gap_eval.run([sample], lambda s: [g.title for g in gaps], threshold=0.6)
    assert summary["micro_f1"] == 1.0 and items[0]["error"] is None


def test_retrieval_eval_smoke():
    summary, items = run_retrieval_eval.run(DeterministicFakeEmbedding(size=64), k=3, only=[SAMPLE])
    assert summary["n_questions"] == 6
    assert all(set(i["ranked_pages"]) <= {1, 2, 3} for i in items)
