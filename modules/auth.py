"""
Authentication Module - Multi-Tenant Ready
===========================================
Password hashing and user DB operations (no UI framework).
"""

import bcrypt
from typing import Optional

from .db import get_db, execute_query


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except Exception:
        return False


def get_user_by_email(email: str) -> Optional[dict]:
    return execute_query(
        "SELECT id, email, password_hash, name, is_active FROM users WHERE email = ?",
        (email.lower().strip(),),
        fetch="one",
    )


def get_user_by_id(user_id: int) -> Optional[dict]:
    return execute_query(
        "SELECT id, email, name, is_active, created_at FROM users WHERE id = ?",
        (user_id,),
        fetch="one",
    )


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

    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
    }


def register(email: str, password: str, name: str) -> Optional[int]:
    email = email.lower().strip()

    if get_user_by_email(email):
        return None

    if len(password) < 6:
        raise ValueError("Sifre en az 6 karakter olmali")

    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)",
            (email, hash_password(password), name.strip()),
        )
        conn.commit()
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
