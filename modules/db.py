"""
Database Core Module - Multi-Tenant Ready
==========================================
Context manager, connection pooling, ve require_user_id decorator.
"""

import sqlite3
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Optional
from datetime import datetime

def get_db_name() -> str:
    try:
        from backend.config import get_settings
        return get_settings().database_path
    except Exception:
        return "LocalInsights.db"


DB_NAME = "LocalInsights.db"  # fallback; prefer get_db_name()


@contextmanager
def get_db():
    """Thread-safe database connection context manager.
    
    Usage:
        with get_db() as conn:
            cursor = conn.execute("SELECT * FROM users")
            results = cursor.fetchall()
    """
    conn = sqlite3.connect(get_db_name(), check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Dict-like access
    conn.execute("PRAGMA foreign_keys = ON")  # FK constraints aktif
    try:
        yield conn
    finally:
        conn.close()


def require_user_id(func: Callable) -> Callable:
    """Decorator: user_id keyword argument olmadan cagriyi engeller.
    
    Guvenlik icin kritik - her veri erisim fonksiyonunda kullanilmali.
    
    Usage:
        @require_user_id
        def get_documents(*, user_id: int):
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        user_id = kwargs.get('user_id')
        if user_id is None:
            raise ValueError(
                f"Security Error: {func.__name__}() requires 'user_id' keyword argument. "
                f"Data access without user context is not allowed."
            )
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(
                f"Security Error: {func.__name__}() requires valid positive integer user_id, "
                f"got: {user_id} ({type(user_id).__name__})"
            )
        return func(*args, **kwargs)
    return wrapper


def execute_query(sql: str, params: tuple = (), fetch: str = 'all') -> Any:
    """Guvenli SQL sorgusu calistirma - parametrized queries.
    
    Args:
        sql: SQL sorgusu (? placeholder'lar ile)
        params: Sorgu parametreleri (tuple)
        fetch: 'all', 'one', veya 'none' (INSERT/UPDATE icin)
    
    Returns:
        fetchall/fetchone sonucu veya lastrowid
    """
    with get_db() as conn:
        cursor = conn.execute(sql, params)
        if fetch == 'all':
            return [dict(row) for row in cursor.fetchall()]
        elif fetch == 'one':
            row = cursor.fetchone()
            return dict(row) if row else None
        else:
            conn.commit()
            return cursor.lastrowid


def execute_many(sql: str, params_list: list) -> int:
    """Bulk insert/update islemleri icin.
    
    Returns:
        Etkilenen satir sayisi
    """
    with get_db() as conn:
        cursor = conn.executemany(sql, params_list)
        conn.commit()
        return cursor.rowcount


# ============== DATABASE INITIALIZATION ==============

def _migrate_existing_tables(conn):
    """Mevcut tablolara user_id kolonu ekler (migration)."""
    tables_to_migrate = ['documents', 'summaries', 'flashcards', 'quiz_questions', 'learning_history']
    
    for table in tables_to_migrate:
        try:
            # Tablo var mi kontrol et
            cursor = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            if not cursor.fetchone():
                continue  # Tablo yok, skip
            
            # user_id kolonu var mi kontrol et
            cursor = conn.execute(f"PRAGMA table_info({table})")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'user_id' not in columns:
                print(f"Migrating {table}: adding user_id column...")
                conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER DEFAULT 1")
                conn.execute(f"UPDATE {table} SET user_id = 1 WHERE user_id IS NULL")
                print(f"Migration complete for {table}")
        except Exception as e:
            print(f"Migration warning for {table}: {e}")

def init_db():
    """Tum tablolari olusturur - multi-tenant ready."""
    with get_db() as conn:
        # Önce users tablosunu oluştur (migration için gerekli)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                name TEXT,
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_login_at DATETIME
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
        
        # Optional default admin (only when SEED_DEFAULT_ADMIN=true)
        try:
            from backend.config import get_settings
            seed_admin = get_settings().seed_default_admin
        except Exception:
            seed_admin = False
        if seed_admin:
            cursor = conn.execute("SELECT id FROM users WHERE id = 1")
            if not cursor.fetchone():
                import bcrypt
                default_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode('utf-8')
                conn.execute(
                    "INSERT OR IGNORE INTO users (id, email, password_hash, name) VALUES (1, 'admin@local', ?, 'Admin')",
                    (default_hash,)
                )
        
        # Mevcut tabloları migrate et (user_id kolonu ekle)
        _migrate_existing_tables(conn)
        
        # CONVERSATIONS tablosu
        conn.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT DEFAULT 'Yeni Sohbet',
                model_name TEXT DEFAULT 'qwen2.5:7b',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id)')
        
        # MESSAGES tablosu
        conn.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id)')
        
        # DOCUMENTS tablosu (user_id ile) - sadece yoksa oluştur
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='documents'")
        if not cursor.fetchone():
            conn.execute('''
                CREATE TABLE documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL DEFAULT 1,
                    filename TEXT NOT NULL,
                    content TEXT,
                    doc_type TEXT,
                    checksum TEXT,
                    upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_processed INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id)')
        
        # SUMMARIES tablosu (user_id ile) - sadece yoksa oluştur
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='summaries'")
        if not cursor.fetchone():
            conn.execute('''
                CREATE TABLE summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL DEFAULT 1,
                    document_id INTEGER,
                    summary_text TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                )
            ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_summaries_user ON summaries(user_id)')
        
        # FLASHCARDS tablosu (user_id ile) - sadece yoksa oluştur
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='flashcards'")
        if not cursor.fetchone():
            conn.execute('''
                CREATE TABLE flashcards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL DEFAULT 1,
                    document_id INTEGER,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    difficulty TEXT DEFAULT 'orta',
                    times_reviewed INTEGER DEFAULT 0,
                    times_correct INTEGER DEFAULT 0,
                    last_reviewed DATETIME,
                    next_review DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                )
            ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_flashcards_user ON flashcards(user_id)')
        
        # QUIZ_QUESTIONS tablosu (user_id ile) - sadece yoksa oluştur
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quiz_questions'")
        if not cursor.fetchone():
            conn.execute('''
                CREATE TABLE quiz_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL DEFAULT 1,
                    document_id INTEGER,
                    question_type TEXT,
                    question_text TEXT NOT NULL,
                    options TEXT,
                    correct_answer TEXT NOT NULL,
                    explanation TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                )
            ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_quiz_user ON quiz_questions(user_id)')
        
        # LEARNING_HISTORY tablosu (user_id ile) - sadece yoksa oluştur
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='learning_history'")
        if not cursor.fetchone():
            conn.execute('''
                CREATE TABLE learning_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL DEFAULT 1,
                    flashcard_id INTEGER,
                    quiz_question_id INTEGER,
                    result TEXT,
                    review_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_learning_user ON learning_history(user_id)')
        
        # MODEL_CALLS tablosu (telemetry)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS model_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                conversation_id INTEGER,
                model_name TEXT NOT NULL,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                latency_ms INTEGER,
                error TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_model_calls_user ON model_calls(user_id)')
        
        # USER_PREFERENCES tablosu (user_id ile + memory_enabled)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                learning_style TEXT DEFAULT 'gorsel',
                difficulty_preference TEXT DEFAULT 'orta',
                daily_goal INTEGER DEFAULT 10,
                memory_enabled INTEGER DEFAULT 1,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_prefs_user ON user_preferences(user_id)')
        
        # Migration: memory_enabled kolonu yoksa ekle
        try:
            cursor = conn.execute("PRAGMA table_info(user_preferences)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'memory_enabled' not in columns:
                conn.execute("ALTER TABLE user_preferences ADD COLUMN memory_enabled INTEGER DEFAULT 1")
        except:
            pass
        
        # MEMORY_ITEMS tablosu (kişiselleştirilmiş hafıza)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS memory_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL DEFAULT 'general',
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                importance REAL DEFAULT 0.5,
                confidence REAL DEFAULT 0.5,
                source_message_id INTEGER,
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, category, key)
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_memory_user ON memory_items(user_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_memory_active ON memory_items(user_id, is_active)')
        
        # USER_PROFILE_SUMMARY tablosu (kısa profil özeti)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_profile_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                summary_text TEXT,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # MEMORY_EVENTS tablosu (hafıza olayları logu)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS memory_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                content TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_memory_events_user ON memory_events(user_id)')

        # COMPILED_NOTES — LangGraph research pipeline output
        conn.execute('''
            CREATE TABLE IF NOT EXISTS compiled_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                document_id INTEGER NOT NULL,
                markdown TEXT,
                gap_list_json TEXT,
                sources_json TEXT,
                status TEXT DEFAULT 'draft',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_compiled_notes_user ON compiled_notes(user_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_compiled_notes_doc ON compiled_notes(document_id)')

        # PIPELINE_JOBS — async compile job status
        conn.execute('''
            CREATE TABLE IF NOT EXISTS pipeline_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                document_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                current_step TEXT,
                error TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_user ON pipeline_jobs(user_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_doc ON pipeline_jobs(document_id)')

        # QUIZ_ATTEMPTS — cozulmus quiz arsivi (ozet)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS quiz_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                document_id INTEGER,
                topic TEXT,
                total_questions INTEGER NOT NULL DEFAULT 0,
                correct_count INTEGER NOT NULL DEFAULT 0,
                score_pct REAL NOT NULL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_quiz_attempts_user ON quiz_attempts(user_id)')

        # QUIZ_ATTEMPT_ITEMS — arsivdeki her sorunun detayi
        conn.execute('''
            CREATE TABLE IF NOT EXISTS quiz_attempt_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attempt_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                question_id INTEGER,
                question_type TEXT,
                question_text TEXT,
                options TEXT,
                given_answer TEXT,
                correct_answer TEXT,
                is_correct INTEGER DEFAULT 0,
                explanation TEXT,
                FOREIGN KEY (attempt_id) REFERENCES quiz_attempts(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_quiz_attempt_items_attempt ON quiz_attempt_items(attempt_id)')

        # STUDY_SESSIONS — calisma oturumlari
        conn.execute('''
            CREATE TABLE IF NOT EXISTS study_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL DEFAULT 'Yeni Çalışma',
                description TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_study_sessions_user ON study_sessions(user_id)')

        _ensure_session_columns(conn)
        _ensure_user_profile_columns(conn)
        _ensure_security_codes_table(conn)
        _backfill_default_sessions(conn)

        conn.commit()


def _ensure_security_codes_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS security_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            purpose TEXT NOT NULL,
            code_hash TEXT NOT NULL,
            attempts INTEGER DEFAULT 0,
            expires_at DATETIME NOT NULL,
            consumed_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_security_codes_user_purpose ON security_codes(user_id, purpose)"
    )


def _ensure_user_profile_columns(conn):
    """users tablosuna username / avatar / oauth alanlarini ekler."""
    try:
        cols = {c[1] for c in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "username" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN username TEXT")
        if "avatar_type" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN avatar_type TEXT DEFAULT 'default'")
        if "avatar_value" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN avatar_value TEXT")
        if "oauth_provider" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN oauth_provider TEXT")
        if "oauth_subject" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN oauth_subject TEXT")
        conn.execute("DROP INDEX IF EXISTS idx_users_username")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username "
            "ON users(username COLLATE NOCASE) "
            "WHERE username IS NOT NULL AND username != ''"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_oauth "
            "ON users(oauth_provider, oauth_subject) "
            "WHERE oauth_provider IS NOT NULL AND oauth_subject IS NOT NULL"
        )
        # Mevcut kullanicilara benzersiz username ata
        rows = conn.execute(
            "SELECT id, email FROM users WHERE username IS NULL OR username = ''"
        ).fetchall()
        for uid, email in rows:
            base = "".join(
                ch for ch in (email or f"user{uid}").split("@")[0].lower() if ch.isalnum() or ch == "_"
            )[:20] or f"user{uid}"
            candidate = base
            n = 0
            while True:
                taken = conn.execute(
                    "SELECT 1 FROM users WHERE username = ? AND id != ?",
                    (candidate, uid),
                ).fetchone()
                if not taken:
                    break
                n += 1
                candidate = f"{base}{n}"
            conn.execute("UPDATE users SET username = ? WHERE id = ?", (candidate, uid))
    except Exception as e:
        print(f"user profile migration warning: {e}")


def _ensure_session_columns(conn):
    """Mevcut tablolara session_id kolonu ekler."""
    tables = [
        "documents",
        "conversations",
        "summaries",
        "flashcards",
        "quiz_questions",
        "compiled_notes",
        "pipeline_jobs",
        "quiz_attempts",
        "learning_history",
    ]
    for table in tables:
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            )
            if not cursor.fetchone():
                continue
            cols = [c[1] for c in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            if "session_id" not in cols:
                print(f"Migrating {table}: adding session_id…")
                conn.execute(f"ALTER TABLE {table} ADD COLUMN session_id INTEGER")
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{table}_session ON {table}(session_id)"
            )
        except Exception as e:
            print(f"session_id migration warning for {table}: {e}")


def _backfill_default_sessions(conn):
    """session_id'siz kayitlari kullanici basina varsayilan oturuma baglar."""
    try:
        users = conn.execute("SELECT id FROM users").fetchall()
        for (uid,) in users:
            row = conn.execute(
                "SELECT id FROM study_sessions WHERE user_id = ? AND is_active = 1 ORDER BY id ASC LIMIT 1",
                (uid,),
            ).fetchone()
            if row:
                sid = row[0]
            else:
                cur = conn.execute(
                    "INSERT INTO study_sessions (user_id, title, description) VALUES (?, ?, ?)",
                    (uid, "Genel Çalışma", "Otomatik oluşturulmuş varsayılan oturum"),
                )
                sid = cur.lastrowid

            for table in (
                "documents",
                "conversations",
                "summaries",
                "flashcards",
                "quiz_questions",
                "compiled_notes",
                "pipeline_jobs",
                "quiz_attempts",
                "learning_history",
            ):
                try:
                    cols = [c[1] for c in conn.execute(f"PRAGMA table_info({table})").fetchall()]
                    if "session_id" in cols and "user_id" in cols:
                        conn.execute(
                            f"UPDATE {table} SET session_id = ? WHERE user_id = ? AND session_id IS NULL",
                            (sid, uid),
                        )
                except Exception:
                    pass
    except Exception as e:
        print(f"session backfill warning: {e}")


def migrate_existing_data(default_user_id: int = 1):
    """Mevcut user_id'siz verileri migrate eder.
    
    NOT: Bu fonksiyon sadece bir kez, migration sirasinda calistirilmali.
    """
    with get_db() as conn:
        # Eski tablolardaki verilere user_id ekle
        tables = ['documents', 'summaries', 'flashcards', 'quiz_questions', 'learning_history']
        
        for table in tables:
            try:
                # user_id kolonu var mi kontrol et
                cursor = conn.execute(f"PRAGMA table_info({table})")
                columns = [col[1] for col in cursor.fetchall()]
                
                if 'user_id' in columns:
                    # NULL olan user_id'leri guncelle
                    conn.execute(
                        f"UPDATE {table} SET user_id = ? WHERE user_id IS NULL",
                        (default_user_id,)
                    )
            except Exception as e:
                print(f"Migration warning for {table}: {e}")
        
        conn.commit()
