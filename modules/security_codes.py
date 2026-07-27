"""Email/password change and password-reset activation codes."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

from backend.config import get_settings
from backend.services.mail import send_activation_code, smtp_configured
from modules.auth import (
    get_user_by_email,
    get_user_by_id,
    get_user_by_username,
    hash_password,
)
from modules.db import execute_query, get_db

PURPOSES = frozenset({"email_change", "password_change", "password_reset"})
MAX_ATTEMPTS = 5
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_code(code: str) -> str:
    secret = get_settings().jwt_secret.encode("utf-8")
    return hmac.new(secret, code.encode("utf-8"), hashlib.sha256).hexdigest()


def _parse_dt(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def resolve_user_by_identifier(identifier: str) -> dict | None:
    """Resolve account by email or username."""
    ident = (identifier or "").strip()
    if not ident:
        return None
    if "@" in ident:
        return get_user_by_email(ident.lower())
    return get_user_by_username(ident) or get_user_by_email(ident.lower())


def request_security_code(
    *,
    user_id: int,
    purpose: str,
    reset_url: str | None = None,
) -> dict:
    if purpose not in PURPOSES:
        raise ValueError("Gecersiz islem")

    user = get_user_by_id(user_id)
    if not user or not user.get("email"):
        raise ValueError("Kullanici bulunamadi")

    settings = get_settings()
    if not smtp_configured() and not settings.debug:
        raise ValueError("E-posta gonderimi yapilandirilmadi")

    cooldown = settings.security_code_cooldown_seconds
    latest = execute_query(
        """SELECT created_at FROM security_codes
           WHERE user_id = ? AND purpose = ?
           ORDER BY id DESC LIMIT 1""",
        (user_id, purpose),
        fetch="one",
    )
    if latest:
        created = _parse_dt(latest.get("created_at"))
        if created and (_utcnow() - created).total_seconds() < cooldown:
            wait = int(cooldown - (_utcnow() - created).total_seconds())
            raise ValueError(f"Yeni kod icin {max(wait, 1)} sn bekleyin")

    code = f"{secrets.randbelow(1_000_000):06d}"
    expires = _utcnow() + timedelta(minutes=settings.security_code_ttl_minutes)

    with get_db() as conn:
        conn.execute(
            """UPDATE security_codes SET consumed_at = CURRENT_TIMESTAMP
               WHERE user_id = ? AND purpose = ? AND consumed_at IS NULL""",
            (user_id, purpose),
        )
        conn.execute(
            """INSERT INTO security_codes (user_id, purpose, code_hash, expires_at)
               VALUES (?, ?, ?, ?)""",
            (user_id, purpose, _hash_code(code), expires.isoformat()),
        )
        conn.commit()

    send_activation_code(
        to=user["email"],
        purpose=purpose,
        code=code,
        reset_url=reset_url if purpose == "password_reset" else None,
    )

    out = {
        "ok": True,
        "purpose": purpose,
        "email_hint": _mask_email(user["email"]),
        "expires_in_seconds": settings.security_code_ttl_minutes * 60,
    }
    if settings.debug and not smtp_configured():
        out["dev_code"] = code
    return out


def request_password_reset(*, identifier: str, reset_url: str | None = None) -> dict:
    """Unauthenticated forgot-password. Always returns a generic ok (anti-enumeration)."""
    generic = {
        "ok": True,
        "message": "Eslesen bir hesap varsa aktivasyon kodu e-postaya gonderildi.",
    }
    user = resolve_user_by_identifier(identifier)
    if not user or not user.get("is_active", True):
        return generic

    try:
        out = request_security_code(
            user_id=user["id"],
            purpose="password_reset",
            reset_url=reset_url,
        )
    except ValueError as e:
        # Surface cooldown so the user can wait; do not leak account existence otherwise.
        if "bekleyin" in str(e).lower():
            raise
        return generic

    result = {
        "ok": True,
        "message": generic["message"],
        "email_hint": out.get("email_hint"),
        "expires_in_seconds": out.get("expires_in_seconds"),
    }
    if out.get("dev_code"):
        result["dev_code"] = out["dev_code"]
    return result


def verify_password_reset(*, identifier: str, code: str) -> dict:
    user = resolve_user_by_identifier(identifier)
    if not user:
        raise ValueError("Gecersiz kod veya hesap")
    return verify_security_code(
        user_id=user["id"],
        purpose="password_reset",
        code=code,
    )


def confirm_password_reset(*, identifier: str, code: str, new_password: str) -> None:
    if len(new_password or "") < 6:
        raise ValueError("Sifre en az 6 karakter olmali")
    user = resolve_user_by_identifier(identifier)
    if not user:
        raise ValueError("Gecersiz kod veya hesap")
    _consume_valid_code(user_id=user["id"], purpose="password_reset", code=code)
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(new_password), user["id"]),
        )
        conn.commit()


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    shown = local[:2] if len(local) > 2 else local[:1]
    return f"{shown}***@{domain}"


def _load_active_code(user_id: int, purpose: str) -> dict | None:
    return execute_query(
        """SELECT id, code_hash, attempts, expires_at, consumed_at
           FROM security_codes
           WHERE user_id = ? AND purpose = ? AND consumed_at IS NULL
           ORDER BY id DESC LIMIT 1""",
        (user_id, purpose),
        fetch="one",
    )


def verify_security_code(*, user_id: int, purpose: str, code: str) -> dict:
    if purpose not in PURPOSES:
        raise ValueError("Gecersiz islem")
    row = _load_active_code(user_id, purpose)
    if not row:
        raise ValueError("Aktif kod bulunamadi; once kod isteyin")

    expires = _parse_dt(row.get("expires_at"))
    if not expires or expires < _utcnow():
        raise ValueError("Kodun suresi dolmus; yeni kod isteyin")

    if int(row.get("attempts") or 0) >= MAX_ATTEMPTS:
        raise ValueError("Cok fazla hatali deneme; yeni kod isteyin")

    ok = hmac.compare_digest(row["code_hash"], _hash_code((code or "").strip()))
    with get_db() as conn:
        if not ok:
            conn.execute(
                "UPDATE security_codes SET attempts = attempts + 1 WHERE id = ?",
                (row["id"],),
            )
            conn.commit()
            raise ValueError("Aktivasyon kodu hatali")
    return {"ok": True, "purpose": purpose}


def _consume_valid_code(*, user_id: int, purpose: str, code: str) -> None:
    verify_security_code(user_id=user_id, purpose=purpose, code=code)
    row = _load_active_code(user_id, purpose)
    if not row:
        raise ValueError("Aktif kod bulunamadi")
    with get_db() as conn:
        conn.execute(
            "UPDATE security_codes SET consumed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (row["id"],),
        )
        conn.commit()


def confirm_email_change(*, user_id: int, code: str, new_email: str) -> dict:
    new_email = (new_email or "").lower().strip()
    if not _EMAIL_RE.match(new_email):
        raise ValueError("Gecersiz e-posta")
    other = get_user_by_email(new_email)
    if other and other["id"] != user_id:
        raise ValueError("Bu e-posta zaten kayitli")

    _consume_valid_code(user_id=user_id, purpose="email_change", code=code)

    with get_db() as conn:
        conn.execute("UPDATE users SET email = ? WHERE id = ?", (new_email, user_id))
        conn.commit()

    user = get_user_by_id(user_id)
    if not user:
        raise ValueError("Kullanici bulunamadi")
    return user


def confirm_password_change(*, user_id: int, code: str, new_password: str) -> None:
    if len(new_password or "") < 6:
        raise ValueError("Sifre en az 6 karakter olmali")
    _consume_valid_code(user_id=user_id, purpose="password_change", code=code)
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(new_password), user_id),
        )
        conn.commit()
