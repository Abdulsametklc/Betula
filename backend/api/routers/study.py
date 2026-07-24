"""Flashcards, quiz, and learning stats routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.auth.deps import CurrentSession, CurrentUser
from backend.llm import default_model_name
from backend.schemas import (
    FlashcardReviewRequest,
    GenerateQuizRequest,
    GenerateStudyRequest,
    QuizAnswerRequest,
    QuizAttemptCreate,
)
from modules.repo_documents import (
    create_flashcards_bulk,
    create_quiz_attempt,
    create_quiz_questions_return_ids,
    delete_quiz_attempt,
    get_archived_quiz_texts,
    get_document,
    get_flashcards,
    get_flashcards_for_review,
    get_learning_stats,
    get_quiz_attempt,
    get_quiz_questions,
    get_random_quiz,
    get_reusable_quiz_questions,
    list_quiz_attempts,
    log_quiz_result,
    update_flashcard_review,
)
from modules.repo_pipeline import get_compiled_note_for_document
from modules.repo_sessions import touch_session
from modules.study_tools import generate_flashcards, generate_quiz

router = APIRouter(tags=["study"])


def _study_source_text(document_id: int, user_id: int) -> str:
    note = get_compiled_note_for_document(document_id, user_id=user_id)
    if note and note.get("markdown"):
        return note["markdown"]
    doc = get_document(document_id, user_id=user_id)
    if doc and doc.get("content"):
        return doc["content"]
    raise HTTPException(status_code=404, detail="Dokuman veya derlenmis not bulunamadi")


def _parse_quiz_options(raw):
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    return [o for o in str(raw).split("|||") if o]


@router.get("/flashcards")
def flashcards_list(user: CurrentUser, document_id: int | None = None):
    return get_flashcards(user_id=user["id"], document_id=document_id)


@router.get("/flashcards/review")
def flashcards_review(
    user: CurrentUser,
    session: CurrentSession,
    limit: int = 50,
    document_id: int | None = None,
):
    return get_flashcards_for_review(
        user_id=user["id"],
        limit=limit,
        document_id=document_id,
        session_id=session["id"],
    )


@router.post("/flashcards/{flashcard_id}/review")
def flashcards_submit_review(flashcard_id: int, body: FlashcardReviewRequest, user: CurrentUser):
    ok = update_flashcard_review(flashcard_id, body.knew, user_id=user["id"])
    if not ok:
        raise HTTPException(status_code=404, detail="Kart bulunamadi")
    return {"ok": True}


@router.post("/documents/{document_id}/flashcards/generate")
def flashcards_generate(
    document_id: int, body: GenerateStudyRequest, user: CurrentUser, session: CurrentSession
):
    text = _study_source_text(document_id, user["id"])
    cards = generate_flashcards(text, count=body.count, model_name=default_model_name())
    if cards:
        create_flashcards_bulk(
            cards,
            user_id=user["id"],
            document_id=document_id,
            session_id=session["id"],
        )
        touch_session(session["id"], user_id=user["id"])
    return {"created": len(cards), "flashcards": cards}


@router.get("/quiz")
def quiz_list(user: CurrentUser, document_id: int | None = None):
    rows = get_quiz_questions(user_id=user["id"], document_id=document_id)
    for r in rows:
        r["options"] = _parse_quiz_options(r.get("options"))
    return rows


@router.get("/quiz/random")
def quiz_random(user: CurrentUser, document_id: int | None = None, limit: int = 10):
    rows = get_random_quiz(user_id=user["id"], document_id=document_id, count=limit)
    for r in rows:
        r["options"] = _parse_quiz_options(r.get("options"))
        # Hide correct answer from client during attempt — keep for answer endpoint
        r.pop("correct_answer", None)
    return rows


@router.post("/quiz/{question_id}/answer")
def quiz_answer(question_id: int, body: QuizAnswerRequest, user: CurrentUser):
    from modules.db import execute_query

    q = execute_query(
        """SELECT id, correct_answer, explanation, options, question_text
           FROM quiz_questions WHERE id = ? AND user_id = ?""",
        (question_id, user["id"]),
        fetch="one",
    )
    if not q:
        raise HTTPException(status_code=404, detail="Soru bulunamadi")

    correct = (q.get("correct_answer") or "").strip()
    given = (body.answer or "").strip()
    is_correct = given.lower() == correct.lower()
    log_quiz_result(question_id, is_correct, user_id=user["id"])
    return {
        "correct": is_correct,
        "correct_answer": correct,
        "explanation": q.get("explanation"),
    }


@router.post("/documents/{document_id}/quiz/generate")
def quiz_generate(
    document_id: int, body: GenerateQuizRequest, user: CurrentUser, session: CurrentSession
):
    """Yeni quiz: arsivlenmis sorular tekrar edilmez.
    Tamamlanmayan (arsive girmemis) sorular yeniden kullanilabilir.
    """
    count = max(1, min(int(body.count or 10), 30))
    uid = user["id"]
    sid = session["id"]

    client_questions = []
    if not (body.topic and str(body.topic).strip()):
        reusable = get_reusable_quiz_questions(
            user_id=uid, document_id=document_id, session_id=sid, limit=count
        )
        client_questions = [
            {
                "id": q["id"],
                "question_type": q.get("question_type") or "multiple_choice",
                "question_text": q.get("question_text") or "",
                "options": q.get("options") or [],
            }
            for q in reusable
            if q.get("options")
        ][:count]

    need = count - len(client_questions)
    if need > 0:
        text = _study_source_text(document_id, uid)
        avoid = get_archived_quiz_texts(user_id=uid, document_id=document_id)
        avoid = avoid + [q["question_text"] for q in client_questions]

        generated = generate_quiz(
            text,
            count=need,
            model_name=default_model_name(),
            topic=body.topic,
            avoid_questions=avoid,
        )
        if generated:
            ids = create_quiz_questions_return_ids(
                generated, user_id=uid, document_id=document_id, session_id=sid
            )
            client_questions.extend(
                {
                    "id": qid,
                    "question_type": q.get("type", "multiple_choice"),
                    "question_text": q["question"],
                    "options": q.get("options", []),
                }
                for qid, q in zip(ids, generated)
            )

    if not client_questions:
        raise HTTPException(
            status_code=502,
            detail="Soru üretilemedi. Farklı bir konu deneyin veya tekrar deneyin.",
        )

    touch_session(sid, user_id=uid)
    return {"created": len(client_questions), "questions": client_questions[:count]}


@router.post("/quiz/attempts")
def quiz_attempt_create(body: QuizAttemptCreate, user: CurrentUser, session: CurrentSession):
    from modules.db import execute_query

    items = []
    for ans in body.answers:
        q = execute_query(
            """SELECT id, question_type, question_text, options, correct_answer, explanation
               FROM quiz_questions WHERE id = ? AND user_id = ?""",
            (ans.question_id, user["id"]),
            fetch="one",
        )
        if not q:
            continue
        correct = (q.get("correct_answer") or "").strip()
        given = (ans.given_answer or "").strip()
        is_correct = given.lower() == correct.lower()
        items.append(
            {
                "question_id": q["id"],
                "question_type": q.get("question_type"),
                "question_text": q.get("question_text"),
                "options": _parse_quiz_options(q.get("options")),
                "given_answer": given,
                "correct_answer": correct,
                "is_correct": is_correct,
                "explanation": q.get("explanation", ""),
            }
        )
        log_quiz_result(q["id"], is_correct, user_id=user["id"])

    if not items:
        raise HTTPException(status_code=400, detail="Kaydedilecek cevap bulunamadi")

    result = create_quiz_attempt(
        user_id=user["id"],
        document_id=body.document_id,
        session_id=session["id"],
        topic=body.topic,
        items=items,
    )
    touch_session(session["id"], user_id=user["id"])
    return result


@router.get("/quiz/attempts")
def quiz_attempts_list(user: CurrentUser, session: CurrentSession):
    return list_quiz_attempts(user_id=user["id"], session_id=session["id"])


@router.get("/quiz/attempts/{attempt_id}")
def quiz_attempt_detail(attempt_id: int, user: CurrentUser):
    attempt = get_quiz_attempt(attempt_id, user_id=user["id"])
    if not attempt:
        raise HTTPException(status_code=404, detail="Deneme bulunamadi")
    return attempt


@router.delete("/quiz/attempts/{attempt_id}")
def quiz_attempt_delete(attempt_id: int, user: CurrentUser):
    ok = delete_quiz_attempt(attempt_id, user_id=user["id"])
    if not ok:
        raise HTTPException(status_code=404, detail="Deneme bulunamadi")
    return {"ok": True}


@router.get("/stats/learning")
def stats_learning(user: CurrentUser):
    return get_learning_stats(user_id=user["id"])
