"""
Documents Repository - Multi-Tenant Ready
==========================================
Document, Summary, Flashcard ve Quiz CRUD islemleri.
Her fonksiyon user_id ile calisir - veri izolasyonu garanti.
"""

from typing import Optional
from .db import get_db, require_user_id, execute_query, execute_many


# ============== DOCUMENT FONKSIYONLARI ==============

@require_user_id
def create_document(filename: str, content: str, doc_type: str, *, user_id: int, checksum: str = None, session_id: int = None) -> int:
    """Yeni dokuman kaydeder."""
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO documents (user_id, session_id, filename, content, doc_type, checksum) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, session_id, filename, content, doc_type, checksum)
        )
        conn.commit()
        return cursor.lastrowid


@require_user_id
def get_documents(*, user_id: int, session_id: int = None, limit: int = 100) -> list:
    """Kullanicinin dokumanlarini listeler (oturum filtresi ile)."""
    if session_id:
        return execute_query(
            """SELECT id, filename, doc_type, upload_date, is_processed, session_id
               FROM documents 
               WHERE user_id = ? AND session_id = ?
               ORDER BY upload_date DESC 
               LIMIT ?""",
            (user_id, session_id, limit),
            fetch='all'
        )
    return execute_query(
        """SELECT id, filename, doc_type, upload_date, is_processed, session_id
           FROM documents 
           WHERE user_id = ? 
           ORDER BY upload_date DESC 
           LIMIT ?""",
        (user_id, limit),
        fetch='all'
    )


@require_user_id
def get_document(document_id: int, *, user_id: int) -> Optional[dict]:
    """Belirli bir dokumani getirir - user_id kontrolu ile.
    
    Args:
        document_id: Dokuman ID
        user_id: Kullanici ID (zorunlu keyword arg)
        
    Returns:
        Document dict veya None
    """
    return execute_query(
        "SELECT * FROM documents WHERE id = ? AND user_id = ?",
        (document_id, user_id),
        fetch='one'
    )


@require_user_id
def delete_document(document_id: int, *, user_id: int) -> bool:
    """Dokumani ve iliskili verileri siler.
    
    Args:
        document_id: Dokuman ID
        user_id: Kullanici ID (zorunlu keyword arg)
        
    Returns:
        True eger silme basarili ise
    """
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM documents WHERE id = ? AND user_id = ?",
            (document_id, user_id)
        )
        conn.commit()
        return cursor.rowcount > 0


@require_user_id
def mark_document_processed(document_id: int, *, user_id: int) -> bool:
    """Dokumani islenmis olarak isaretler.
    
    Args:
        document_id: Dokuman ID
        user_id: Kullanici ID (zorunlu keyword arg)
        
    Returns:
        True eger guncelleme basarili ise
    """
    with get_db() as conn:
        cursor = conn.execute(
            "UPDATE documents SET is_processed = 1 WHERE id = ? AND user_id = ?",
            (document_id, user_id)
        )
        conn.commit()
        return cursor.rowcount > 0


# ============== SUMMARY FONKSIYONLARI ==============

@require_user_id
def create_summary(document_id: int, summary_text: str, *, user_id: int) -> int:
    """Yeni ozet kaydeder.
    
    Args:
        document_id: Ilgili dokuman ID
        summary_text: Ozet metni
        user_id: Kullanici ID (zorunlu keyword arg)
        
    Returns:
        Yeni summary_id
    """
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO summaries (user_id, document_id, summary_text) 
               VALUES (?, ?, ?)""",
            (user_id, document_id, summary_text)
        )
        conn.commit()
        return cursor.lastrowid


@require_user_id
def get_summaries(*, user_id: int, document_id: int = None, limit: int = 50) -> list:
    """Kullanicinin ozetlerini listeler.
    
    Args:
        user_id: Kullanici ID (zorunlu keyword arg)
        document_id: Belirli dokumana ait ozetler (opsiyonel)
        limit: Maksimum kayit sayisi
        
    Returns:
        Summary listesi
    """
    if document_id:
        return execute_query(
            """SELECT s.id, d.filename, s.summary_text, s.created_at 
               FROM summaries s 
               JOIN documents d ON s.document_id = d.id 
               WHERE s.user_id = ? AND s.document_id = ?
               ORDER BY s.created_at DESC LIMIT ?""",
            (user_id, document_id, limit),
            fetch='all'
        )
    else:
        return execute_query(
            """SELECT s.id, d.filename, s.summary_text, s.created_at 
               FROM summaries s 
               JOIN documents d ON s.document_id = d.id 
               WHERE s.user_id = ?
               ORDER BY s.created_at DESC LIMIT ?""",
            (user_id, limit),
            fetch='all'
        )


# ============== FLASHCARD FONKSIYONLARI ==============

@require_user_id
def create_flashcard(question: str, answer: str, *, user_id: int, document_id: int = None, difficulty: str = 'orta') -> int:
    """Yeni flashcard kaydeder.
    
    Args:
        question: Soru
        answer: Cevap
        user_id: Kullanici ID (zorunlu keyword arg)
        document_id: Ilgili dokuman (opsiyonel)
        difficulty: Zorluk seviyesi
        
    Returns:
        Yeni flashcard_id
    """
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO flashcards (user_id, document_id, question, answer, difficulty) 
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, document_id, question, answer, difficulty)
        )
        conn.commit()
        return cursor.lastrowid


@require_user_id
def create_flashcards_bulk(flashcards_list: list, *, user_id: int, document_id: int = None, session_id: int = None) -> int:
    """Birden fazla flashcard kaydeder."""
    params_list = [
        (user_id, session_id, document_id, card['question'], card['answer'], card.get('difficulty', 'orta'))
        for card in flashcards_list
    ]
    return execute_many(
        "INSERT INTO flashcards (user_id, session_id, document_id, question, answer, difficulty) VALUES (?, ?, ?, ?, ?, ?)",
        params_list
    )


@require_user_id
def get_flashcards(*, user_id: int, document_id: int = None, limit: int = 100) -> list:
    """Kullanicinin flashcard'larini listeler.
    
    Args:
        user_id: Kullanici ID (zorunlu keyword arg)
        document_id: Belirli dokumana ait kartlar (opsiyonel)
        limit: Maksimum kayit sayisi
        
    Returns:
        Flashcard listesi
    """
    if document_id:
        return execute_query(
            """SELECT f.id, d.filename, f.question, f.answer, f.difficulty, 
                      f.times_reviewed, f.times_correct, f.next_review
               FROM flashcards f 
               LEFT JOIN documents d ON f.document_id = d.id 
               WHERE f.user_id = ? AND f.document_id = ?
               ORDER BY f.created_at DESC LIMIT ?""",
            (user_id, document_id, limit),
            fetch='all'
        )
    else:
        return execute_query(
            """SELECT f.id, d.filename, f.question, f.answer, f.difficulty,
                      f.times_reviewed, f.times_correct, f.next_review
               FROM flashcards f 
               LEFT JOIN documents d ON f.document_id = d.id 
               WHERE f.user_id = ?
               ORDER BY f.created_at DESC LIMIT ?""",
            (user_id, limit),
            fetch='all'
        )


@require_user_id
def get_flashcards_for_review(*, user_id: int, limit: int = 50, document_id: int = None, session_id: int = None) -> list:
    """Kartlari sirayla gostermek icin listeler."""
    if document_id:
        return execute_query(
            """SELECT f.id, d.filename, f.question, f.answer, f.difficulty, f.times_reviewed
               FROM flashcards f 
               LEFT JOIN documents d ON f.document_id = d.id 
               WHERE f.user_id = ? AND f.document_id = ?
               ORDER BY f.id ASC
               LIMIT ?""",
            (user_id, document_id, limit),
            fetch='all'
        )
    if session_id:
        return execute_query(
            """SELECT f.id, d.filename, f.question, f.answer, f.difficulty, f.times_reviewed
               FROM flashcards f 
               LEFT JOIN documents d ON f.document_id = d.id 
               WHERE f.user_id = ? AND f.session_id = ?
               ORDER BY f.id ASC
               LIMIT ?""",
            (user_id, session_id, limit),
            fetch='all'
        )
    return execute_query(
        """SELECT f.id, d.filename, f.question, f.answer, f.difficulty, f.times_reviewed
           FROM flashcards f 
           LEFT JOIN documents d ON f.document_id = d.id 
           WHERE f.user_id = ?
           ORDER BY f.id ASC
           LIMIT ?""",
        (user_id, limit),
        fetch='all'
    )


@require_user_id
def update_flashcard_review(flashcard_id: int, is_correct: bool, *, user_id: int) -> bool:
    """Kart bakildi olarak isaretler (sadece sayac + history; tarih plani yok)."""
    card = execute_query(
        "SELECT times_reviewed, times_correct FROM flashcards WHERE id = ? AND user_id = ?",
        (flashcard_id, user_id),
        fetch='one'
    )
    if not card:
        return False

    times_reviewed = card['times_reviewed'] + 1
    times_correct = card['times_correct'] + (1 if is_correct else 0)

    with get_db() as conn:
        conn.execute(
            """UPDATE flashcards 
               SET times_reviewed = ?, times_correct = ?, last_reviewed = datetime('now')
               WHERE id = ? AND user_id = ?""",
            (times_reviewed, times_correct, flashcard_id, user_id)
        )
        conn.execute(
            "INSERT INTO learning_history (user_id, flashcard_id, result) VALUES (?, ?, ?)",
            (user_id, flashcard_id, 'correct' if is_correct else 'incorrect')
        )
        conn.commit()
        return True


# ============== QUIZ FONKSIYONLARI ==============

@require_user_id
def create_quiz_question(
    question_text: str, 
    correct_answer: str, 
    *, 
    user_id: int,
    document_id: int = None,
    question_type: str = 'multiple_choice',
    options: str = '',
    explanation: str = ''
) -> int:
    """Yeni quiz sorusu kaydeder.
    
    Args:
        question_text: Soru metni
        correct_answer: Dogru cevap
        user_id: Kullanici ID (zorunlu keyword arg)
        document_id: Ilgili dokuman (opsiyonel)
        question_type: Soru tipi
        options: Secenekler (||| ile ayrilmis)
        explanation: Aciklama
        
    Returns:
        Yeni question_id
    """
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO quiz_questions 
               (user_id, document_id, question_type, question_text, options, correct_answer, explanation) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, document_id, question_type, question_text, options, correct_answer, explanation)
        )
        conn.commit()
        return cursor.lastrowid


@require_user_id
def create_quiz_questions_bulk(questions_list: list, *, user_id: int, document_id: int = None) -> int:
    """Birden fazla quiz sorusu kaydeder.
    
    Args:
        questions_list: [{'question': '...', 'answer': '...', 'type': '...', 'options': [...], 'explanation': '...'}, ...]
        user_id: Kullanici ID (zorunlu keyword arg)
        document_id: Ilgili dokuman (opsiyonel)
        
    Returns:
        Eklenen kayit sayisi
    """
    params_list = [
        (
            user_id, 
            document_id, 
            q.get('type', 'multiple_choice'),
            q['question'], 
            '|||'.join(q.get('options', [])) if q.get('options') else '',
            q['answer'],
            q.get('explanation', '')
        )
        for q in questions_list
    ]
    return execute_many(
        """INSERT INTO quiz_questions 
           (user_id, document_id, question_type, question_text, options, correct_answer, explanation) 
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        params_list
    )


@require_user_id
def create_quiz_questions_return_ids(questions_list: list, *, user_id: int, document_id: int = None, session_id: int = None) -> list:
    """Sorulari tek tek kaydeder ve olusan id'leri sirayla dondurur."""
    ids = []
    with get_db() as conn:
        for q in questions_list:
            cursor = conn.execute(
                """INSERT INTO quiz_questions 
                   (user_id, session_id, document_id, question_type, question_text, options, correct_answer, explanation) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    session_id,
                    document_id,
                    q.get('type', 'multiple_choice'),
                    q['question'],
                    '|||'.join(q.get('options', [])) if q.get('options') else '',
                    q['answer'],
                    q.get('explanation', ''),
                ),
            )
            ids.append(cursor.lastrowid)
        conn.commit()
    return ids


@require_user_id
def get_archived_quiz_texts(*, user_id: int, document_id: int = None, limit: int = 300) -> list:
    """Tamamlanip arsivlenen quiz soru metinlerini dondurur (tekrar sorulmamali).
    Yarim kalan quiz'lerdeki sorular buraya girmez; tekrar sorulabilir.
    """
    if document_id:
        rows = execute_query(
            """SELECT DISTINCT i.question_text
               FROM quiz_attempt_items i
               JOIN quiz_attempts a ON a.id = i.attempt_id
               WHERE i.user_id = ? AND a.user_id = ? AND a.document_id = ?
                 AND i.question_text IS NOT NULL AND TRIM(i.question_text) != ''
               ORDER BY i.id DESC LIMIT ?""",
            (user_id, user_id, document_id, limit),
            fetch='all',
        )
    else:
        rows = execute_query(
            """SELECT DISTINCT i.question_text
               FROM quiz_attempt_items i
               JOIN quiz_attempts a ON a.id = i.attempt_id
               WHERE i.user_id = ? AND a.user_id = ?
                 AND i.question_text IS NOT NULL AND TRIM(i.question_text) != ''
               ORDER BY i.id DESC LIMIT ?""",
            (user_id, user_id, limit),
            fetch='all',
        )
    return [r['question_text'] for r in rows if r.get('question_text')]


@require_user_id
def get_reusable_quiz_questions(
    *,
    user_id: int,
    document_id: int = None,
    session_id: int = None,
    limit: int = 50,
    topic: str = None,
) -> list:
    """Arsivde olmayan (tamamlanmamis) sorulari rastgele dondurur — tekrar sorulabilir."""
    params: list = [user_id]
    sql = """
        SELECT q.id, q.question_type, q.question_text, q.options
        FROM quiz_questions q
        WHERE q.user_id = ?
          AND q.id NOT IN (
              SELECT DISTINCT question_id FROM quiz_attempt_items
              WHERE user_id = ? AND question_id IS NOT NULL
          )
    """
    params.append(user_id)
    if session_id:
        sql += " AND q.session_id = ?"
        params.append(session_id)
    if document_id:
        sql += " AND q.document_id = ?"
        params.append(document_id)
    sql += " ORDER BY RANDOM() LIMIT ?"
    params.append(limit)
    rows = execute_query(sql, tuple(params), fetch='all')
    for r in rows:
        raw = r.get('options')
        r['options'] = [o for o in str(raw).split('|||') if o] if raw else []
    return rows


@require_user_id
def get_quiz_questions_by_ids(ids: list, *, user_id: int) -> list:
    """Belirtilen id'lere sahip sorulari (cevapsiz) dondurur - sira korunur."""
    if not ids:
        return []
    placeholders = ','.join('?' for _ in ids)
    rows = execute_query(
        f"""SELECT id, question_type, question_text, options, explanation
            FROM quiz_questions WHERE user_id = ? AND id IN ({placeholders})""",
        (user_id, *ids),
        fetch='all',
    )
    by_id = {r['id']: r for r in rows}
    return [by_id[i] for i in ids if i in by_id]


@require_user_id
def create_quiz_attempt(*, user_id: int, document_id: int = None, session_id: int = None, topic: str = None, items: list) -> dict:
    """Cozulmus quiz'i arsivler."""
    total = len(items)
    correct = sum(1 for it in items if it.get('is_correct'))
    score = round(correct * 100.0 / total, 1) if total else 0.0

    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO quiz_attempts 
               (user_id, session_id, document_id, topic, total_questions, correct_count, score_pct) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, session_id, document_id, topic, total, correct, score),
        )
        attempt_id = cursor.lastrowid
        for it in items:
            opts = it.get('options') or []
            conn.execute(
                """INSERT INTO quiz_attempt_items 
                   (attempt_id, user_id, question_id, question_type, question_text, options,
                    given_answer, correct_answer, is_correct, explanation) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    attempt_id,
                    user_id,
                    it.get('question_id'),
                    it.get('question_type'),
                    it.get('question_text'),
                    '|||'.join(opts) if isinstance(opts, list) else str(opts or ''),
                    it.get('given_answer'),
                    it.get('correct_answer'),
                    1 if it.get('is_correct') else 0,
                    it.get('explanation', ''),
                ),
            )
        conn.commit()

    return {
        'id': attempt_id,
        'total_questions': total,
        'correct_count': correct,
        'score_pct': score,
    }


@require_user_id
def list_quiz_attempts(*, user_id: int, session_id: int = None, limit: int = 50) -> list:
    """Kullanicinin quiz arsivini (ozet) listeler."""
    if session_id:
        return execute_query(
            """SELECT a.id, a.document_id, d.filename, a.topic, a.total_questions,
                      a.correct_count, a.score_pct, a.created_at
               FROM quiz_attempts a
               LEFT JOIN documents d ON a.document_id = d.id
               WHERE a.user_id = ? AND a.session_id = ?
               ORDER BY a.created_at DESC LIMIT ?""",
            (user_id, session_id, limit),
            fetch='all',
        )
    return execute_query(
        """SELECT a.id, a.document_id, d.filename, a.topic, a.total_questions,
                  a.correct_count, a.score_pct, a.created_at
           FROM quiz_attempts a
           LEFT JOIN documents d ON a.document_id = d.id
           WHERE a.user_id = ?
           ORDER BY a.created_at DESC LIMIT ?""",
        (user_id, limit),
        fetch='all',
    )


@require_user_id
def get_quiz_attempt(attempt_id: int, *, user_id: int) -> Optional[dict]:
    """Bir quiz denemesinin detayini (sorularla) dondurur."""
    attempt = execute_query(
        """SELECT a.id, a.document_id, d.filename, a.topic, a.total_questions,
                  a.correct_count, a.score_pct, a.created_at
           FROM quiz_attempts a
           LEFT JOIN documents d ON a.document_id = d.id
           WHERE a.id = ? AND a.user_id = ?""",
        (attempt_id, user_id),
        fetch='one',
    )
    if not attempt:
        return None
    items = execute_query(
        """SELECT question_id, question_type, question_text, options,
                  given_answer, correct_answer, is_correct, explanation
           FROM quiz_attempt_items WHERE attempt_id = ? AND user_id = ?
           ORDER BY id ASC""",
        (attempt_id, user_id),
        fetch='all',
    )
    for it in items:
        raw = it.get('options')
        it['options'] = [o for o in str(raw).split('|||') if o] if raw else []
        it['is_correct'] = bool(it.get('is_correct'))
    attempt['items'] = items
    return attempt


@require_user_id
def delete_quiz_attempt(attempt_id: int, *, user_id: int) -> bool:
    """Bir quiz denemesini arsivden siler."""
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM quiz_attempts WHERE id = ? AND user_id = ?",
            (attempt_id, user_id),
        )
        conn.commit()
        return cursor.rowcount > 0


@require_user_id
def get_quiz_questions(*, user_id: int, document_id: int = None, limit: int = 100) -> list:
    """Kullanicinin quiz sorularini listeler.
    
    Args:
        user_id: Kullanici ID (zorunlu keyword arg)
        document_id: Belirli dokumana ait sorular (opsiyonel)
        limit: Maksimum kayit sayisi
        
    Returns:
        Quiz question listesi
    """
    if document_id:
        return execute_query(
            """SELECT q.id, d.filename, q.question_type, q.question_text, 
                      q.options, q.correct_answer, q.explanation
               FROM quiz_questions q 
               LEFT JOIN documents d ON q.document_id = d.id 
               WHERE q.user_id = ? AND q.document_id = ?
               ORDER BY q.created_at DESC LIMIT ?""",
            (user_id, document_id, limit),
            fetch='all'
        )
    else:
        return execute_query(
            """SELECT q.id, d.filename, q.question_type, q.question_text,
                      q.options, q.correct_answer, q.explanation
               FROM quiz_questions q 
               LEFT JOIN documents d ON q.document_id = d.id 
               WHERE q.user_id = ?
               ORDER BY q.created_at DESC LIMIT ?""",
            (user_id, limit),
            fetch='all'
        )


@require_user_id
def get_random_quiz(*, user_id: int, document_id: int = None, count: int = 10) -> list:
    """Rastgele quiz sorulari getirir.
    
    Args:
        user_id: Kullanici ID (zorunlu keyword arg)
        document_id: Belirli dokumandan sorular (opsiyonel)
        count: Soru sayisi
        
    Returns:
        Rastgele quiz soruları
    """
    if document_id:
        return execute_query(
            """SELECT id, question_type, question_text, options, correct_answer, explanation
               FROM quiz_questions 
               WHERE user_id = ? AND document_id = ?
               ORDER BY RANDOM() LIMIT ?""",
            (user_id, document_id, count),
            fetch='all'
        )
    else:
        return execute_query(
            """SELECT id, question_type, question_text, options, correct_answer, explanation
               FROM quiz_questions 
               WHERE user_id = ?
               ORDER BY RANDOM() LIMIT ?""",
            (user_id, count),
            fetch='all'
        )


@require_user_id
def log_quiz_result(quiz_question_id: int, is_correct: bool, *, user_id: int) -> int:
    """Quiz sonucunu kaydeder.
    
    Args:
        quiz_question_id: Soru ID
        is_correct: Dogru mu yanlis mi
        user_id: Kullanici ID (zorunlu keyword arg)
        
    Returns:
        Log ID
    """
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO learning_history (user_id, quiz_question_id, result) VALUES (?, ?, ?)",
            (user_id, quiz_question_id, 'correct' if is_correct else 'incorrect')
        )
        conn.commit()
        return cursor.lastrowid


# ============== ISTATISTIK FONKSIYONLARI ==============

@require_user_id
def get_learning_stats(*, user_id: int) -> dict:
    """Kullanicinin ogrenme istatistiklerini getirir.
    
    Args:
        user_id: Kullanici ID (zorunlu keyword arg)
        
    Returns:
        Istatistik dict
    """
    with get_db() as conn:
        stats = {}
        
        # Toplam dokuman sayisi
        cursor = conn.execute("SELECT COUNT(*) FROM documents WHERE user_id = ?", (user_id,))
        stats['total_documents'] = cursor.fetchone()[0]
        
        # Toplam flashcard sayisi
        cursor = conn.execute("SELECT COUNT(*) FROM flashcards WHERE user_id = ?", (user_id,))
        stats['total_flashcards'] = cursor.fetchone()[0]
        
        # Toplam soru sayisi
        cursor = conn.execute("SELECT COUNT(*) FROM quiz_questions WHERE user_id = ?", (user_id,))
        stats['total_questions'] = cursor.fetchone()[0]
        
        # Bugun tekrar edilen kart sayisi
        cursor = conn.execute(
            """SELECT COUNT(*) FROM learning_history 
               WHERE user_id = ? AND flashcard_id IS NOT NULL AND date(review_date) = date('now')""",
            (user_id,)
        )
        stats['cards_reviewed_today'] = cursor.fetchone()[0]
        
        # Genel basari orani
        cursor = conn.execute(
            """SELECT COUNT(CASE WHEN result = 'correct' THEN 1 END) * 100.0 / COUNT(*) 
               FROM learning_history 
               WHERE user_id = ? AND result IS NOT NULL""",
            (user_id,)
        )
        result = cursor.fetchone()[0]
        stats['success_rate'] = round(result, 1) if result else 0
        
        return stats
