"""
Authentication Module - Multi-Tenant Ready
===========================================
Password hashing and user DB operations (no UI framework).
"""

from __future__ import annotations

import re
from typing import Optional

import bcrypt

from .db import execute_query, get_db

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash or str(password_hash).startswith("oauth:"):
        return False
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except Exception:
        return False


def _public_user(row: dict) -> dict:
    return {
        "id": row["id"],
        "email": row["email"],
        "name": row.get("name"),
        "username": row.get("username"),
        "avatar_type": row.get("avatar_type") or "default",
        "avatar_value": row.get("avatar_value"),
    }


def get_user_by_oauth(provider: str, subject: str) -> Optional[dict]:
    return execute_query(
        """SELECT id, email, password_hash, name, username, avatar_type, avatar_value, is_active,
                  oauth_provider, oauth_subject
           FROM users WHERE oauth_provider = ? AND oauth_subject = ?""",
        (provider, subject),
        fetch="one",
    )


def upsert_oauth_user(
    *,
    provider: str,
    subject: str,
    email: str,
    name: str | None = None,
) -> dict:
    """Create or link a user from an OAuth identity. Returns public user dict."""
    provider = (provider or "").strip().lower()
    subject = (subject or "").strip()
    email = (email or "").lower().strip()
    if provider not in {"google", "github"} or not subject:
        raise ValueError("Gecersiz OAuth kimligi")
    if not email or not _EMAIL_RE.match(email):
        raise ValueError("OAuth hesabinda e-posta bulunamadi")

    existing = get_user_by_oauth(provider, subject)
    if existing:
        with get_db() as conn:
            conn.execute(
                "UPDATE users SET last_login_at = CURRENT_TIMESTAMP, name = COALESCE(?, name) WHERE id = ?",
                ((name or "").strip() or None, existing["id"]),
            )
            conn.commit()
        user = get_user_by_id(existing["id"]) or existing
        return _public_user(user)

    by_email = get_user_by_email(email)
    if by_email:
        with get_db() as conn:
            conn.execute(
                """UPDATE users
                   SET oauth_provider = ?, oauth_subject = ?,
                       last_login_at = CURRENT_TIMESTAMP,
                       name = COALESCE(?, name)
                   WHERE id = ?""",
                (provider, subject, (name or "").strip() or None, by_email["id"]),
            )
            conn.commit()
        user = get_user_by_id(by_email["id"]) or by_email
        return _public_user(user)

    display = (name or "").strip() or email.split("@")[0]
    with get_db() as conn:
        uname = _unique_username(conn, email.split("@")[0])
        cursor = conn.execute(
            """INSERT INTO users
               (email, password_hash, name, username, avatar_type, oauth_provider, oauth_subject, last_login_at)
               VALUES (?, ?, ?, ?, 'default', ?, ?, CURRENT_TIMESTAMP)""",
            (email, f"oauth:{provider}", display, uname, provider, subject),
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.execute("INSERT INTO user_preferences (user_id) VALUES (?)", (user_id,))
        conn.commit()

    user = get_user_by_id(user_id)
    if not user:
        raise ValueError("OAuth kullanici olusturulamadi")
    return _public_user(user)


def get_user_by_email(email: str) -> Optional[dict]:
    return execute_query(
        """SELECT id, email, password_hash, name, username, avatar_type, avatar_value, is_active
           FROM users WHERE email = ?""",
        (email.lower().strip(),),
        fetch="one",
    )


def get_user_by_username(username: str) -> Optional[dict]:
    return execute_query(
        """SELECT id, email, password_hash, name, username, avatar_type, avatar_value, is_active
           FROM users WHERE username = ? COLLATE NOCASE""",
        (username.strip(),),
        fetch="one",
    )


def get_user_by_id(user_id: int) -> Optional[dict]:
    return execute_query(
        """SELECT id, email, name, username, avatar_type, avatar_value, is_active, created_at
           FROM users WHERE id = ?""",
        (user_id,),
        fetch="one",
    )


def _unique_username(conn, base: str, exclude_id: int | None = None) -> str:
    clean = "".join(ch for ch in base.lower() if ch.isalnum() or ch == "_")[:20] or "user"
    candidate = clean
    n = 0
    while True:
        q = "SELECT 1 FROM users WHERE username = ? COLLATE NOCASE"
        params: list = [candidate]
        if exclude_id is not None:
            q += " AND id != ?"
            params.append(exclude_id)
        if not conn.execute(q, tuple(params)).fetchone():
            return candidate
        n += 1
        candidate = f"{clean}{n}"


def login(email: str, password: str) -> Optional[dict]:
    email = email.lower().strip()
    user = get_user_by_email(email)

    if not user:
        return None
    if not user.get("is_active", True):
        return None
    if not verify_password(password, user["password_hash"]):
        return None

    with get_db() as conn:
        conn.execute(
            "UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?",
            (user["id"],),
        )
        conn.commit()

    return _public_user(user)


def register(email: str, password: str, name: str, username: str | None = None) -> Optional[int]:
    email = email.lower().strip()

    if get_user_by_email(email):
        return None

    if len(password) < 6:
        raise ValueError("Sifre en az 6 karakter olmali")

    with get_db() as conn:
        uname = (username or "").strip()
        if uname:
            if not _USERNAME_RE.match(uname):
                raise ValueError("Kullanici adi 3-32 karakter, harf/rakam/_ olmali")
            if conn.execute(
                "SELECT 1 FROM users WHERE username = ? COLLATE NOCASE", (uname,)
            ).fetchone():
                raise ValueError("Bu kullanici adi zaten alinmis")
        else:
            uname = _unique_username(conn, email.split("@")[0])

        try:
            cursor = conn.execute(
                """INSERT INTO users (email, password_hash, name, username, avatar_type)
                   VALUES (?, ?, ?, ?, 'default')""",
                (email, hash_password(password), name.strip(), uname),
            )
            conn.commit()
        except Exception as e:
            msg = str(e).lower()
            if "unique" in msg:
                if "username" in msg:
                    raise ValueError("Bu kullanici adi zaten alinmis") from e
                raise ValueError("Bu e-posta zaten kayitli") from e
            raise
        user_id = cursor.lastrowid

        conn.execute(
            "INSERT INTO user_preferences (user_id) VALUES (?)",
            (user_id,),
        )
        conn.commit()
        return user_id


def update_password(user_id: int, old_password: str, new_password: str) -> bool:
    user = execute_query(
        "SELECT password_hash FROM users WHERE id = ?",
        (user_id,),
        fetch="one",
    )

    if not user or not verify_password(old_password, user["password_hash"]):
        return False

    if len(new_password) < 6:
        return False

    with get_db() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(new_password), user_id),
        )
        conn.commit()

    return True


def update_profile(
    user_id: int,
    *,
    name: str | None = None,
    username: str | None = None,
) -> dict:
    """Profil alanlarini gunceller (isim / kullanici adi)."""
    row = execute_query(
        """SELECT id, email, password_hash, name, username, avatar_type, avatar_value, is_active
           FROM users WHERE id = ?""",
        (user_id,),
        fetch="one",
    )
    if not row:
        raise ValueError("Kullanici bulunamadi")

    fields: list[str] = []
    params: list = []

    if name is not None:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("Isim bos olamaz")
        fields.append("name = ?")
        params.append(cleaned)

    if username is not None:
        uname = username.strip()
        if not _USERNAME_RE.match(uname):
            raise ValueError("Kullanici adi 3-32 karakter, harf/rakam/_ olmali")
        other = get_user_by_username(uname)
        if other and other["id"] != user_id:
            raise ValueError("Bu kullanici adi zaten alinmis")
        fields.append("username = ?")
        params.append(uname)

    if not fields:
        return _public_user(row)

    params.append(user_id)
    with get_db() as conn:
        try:
            conn.execute(
                f"UPDATE users SET {', '.join(fields)} WHERE id = ?",
                tuple(params),
            )
            conn.commit()
        except Exception as e:
            msg = str(e).lower()
            if "unique" in msg or "username" in msg:
                raise ValueError("Bu kullanici adi zaten alinmis") from e
            raise

    updated = get_user_by_id(user_id)
    return _public_user(updated or row)


def set_avatar(user_id: int, avatar_type: str, avatar_value: str | None) -> dict:
    if avatar_type not in ("default", "icon", "image"):
        raise ValueError("Gecersiz avatar tipi")
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET avatar_type = ?, avatar_value = ? WHERE id = ?",
            (avatar_type, avatar_value, user_id),
        )
        conn.commit()
    user = get_user_by_id(user_id)
    if not user:
        raise ValueError("Kullanici bulunamadi")
    return _public_user(user)
