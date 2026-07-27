"""Google / GitHub OAuth helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from backend.config import get_settings

PROVIDERS = ("google", "github")


def configured_providers() -> dict[str, bool]:
    s = get_settings()
    return {
        "google": s.google_oauth_configured(),
        "github": s.github_oauth_configured(),
    }


def _sign_state(payload: str) -> str:
    secret = get_settings().jwt_secret.encode("utf-8")
    sig = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def _verify_state(state: str) -> dict[str, str]:
    try:
        payload, sig = state.rsplit(".", 1)
    except ValueError as e:
        raise ValueError("Gecersiz OAuth state") from e
    expected = hmac.new(
        get_settings().jwt_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise ValueError("Gecersiz OAuth state")
    parts = dict(item.split("=", 1) for item in payload.split("&") if "=" in item)
    ts = int(parts.get("ts", "0"))
    if abs(int(time.time()) - ts) > 600:
        raise ValueError("OAuth oturumu suresi doldu")
    provider = parts.get("p", "")
    if provider not in PROVIDERS:
        raise ValueError("Gecersiz OAuth saglayici")
    return {"provider": provider, "nonce": parts.get("n", "")}


def make_state(provider: str) -> str:
    nonce = secrets.token_urlsafe(12)
    payload = f"p={provider}&n={nonce}&ts={int(time.time())}"
    return _sign_state(payload)


def oauth_base_url(request_base: str | None = None) -> str:
    """Prefer PUBLIC_BASE_URL so redirect_uri always matches Google Console."""
    configured = (get_settings().public_base_url or "").strip().rstrip("/")
    if configured:
        return configured
    return (request_base or "http://127.0.0.1:8000").rstrip("/")


def callback_url(provider: str, base_url: str | None = None) -> str:
    base = oauth_base_url(base_url)
    return f"{base}/auth/oauth/{provider}/callback"


def authorization_url(provider: str, *, base_url: str | None = None) -> tuple[str, str]:
    """Return (authorize_url, state)."""
    s = get_settings()
    provider = provider.lower().strip()
    state = make_state(provider)
    redirect_uri = callback_url(provider, base_url)

    if provider == "google":
        if not s.google_oauth_configured():
            raise ValueError("Google OAuth yapilandirilmadi")
        params = {
            "client_id": s.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "online",
            "include_granted_scopes": "true",
            "prompt": "select_account",
            "state": state,
        }
        url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
        return url, state

    if provider == "github":
        if not s.github_oauth_configured():
            raise ValueError("GitHub OAuth yapilandirilmadi")
        params = {
            "client_id": s.github_client_id,
            "redirect_uri": redirect_uri,
            "scope": "read:user user:email",
            "state": state,
            "allow_signup": "true",
        }
        url = "https://github.com/login/oauth/authorize?" + urlencode(params)
        return url, state

    raise ValueError("Desteklenmeyen OAuth saglayici")


def exchange_code(
    provider: str,
    *,
    code: str,
    state: str,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Validate state, exchange code, return {provider, subject, email, name}."""
    meta = _verify_state(state)
    if meta["provider"] != provider:
        raise ValueError("OAuth state uyusmuyor")

    if provider == "google":
        return _google_profile(code=code, base_url=base_url)
    if provider == "github":
        return _github_profile(code=code, base_url=base_url)
    raise ValueError("Desteklenmeyen OAuth saglayici")


def _google_profile(*, code: str, base_url: str | None) -> dict[str, Any]:
    s = get_settings()
    redirect_uri = callback_url("google", base_url)
    with httpx.Client(timeout=20.0) as client:
        token_res = client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": s.google_client_id,
                "client_secret": s.google_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_res.status_code >= 400:
            raise ValueError("Google token alinamadi")
        access = token_res.json().get("access_token")
        if not access:
            raise ValueError("Google access_token yok")
        info = client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access}"},
        )
        if info.status_code >= 400:
            raise ValueError("Google profil alinamadi")
        data = info.json()

    email = (data.get("email") or "").strip()
    if not email or not data.get("email_verified", True):
        raise ValueError("Google hesabinda dogrulanmis e-posta yok")
    return {
        "provider": "google",
        "subject": str(data.get("sub") or ""),
        "email": email,
        "name": (data.get("name") or data.get("given_name") or "").strip() or None,
    }


def _github_profile(*, code: str, base_url: str | None) -> dict[str, Any]:
    s = get_settings()
    redirect_uri = callback_url("github", base_url)
    headers = {
        "Accept": "application/json",
        "User-Agent": "Betula-OAuth",
    }
    with httpx.Client(timeout=20.0, headers=headers) as client:
        token_res = client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": s.github_client_id,
                "client_secret": s.github_client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        if token_res.status_code >= 400:
            raise ValueError("GitHub token alinamadi")
        token_data = token_res.json()
        access = token_data.get("access_token")
        if not access:
            raise ValueError(token_data.get("error_description") or "GitHub access_token yok")

        auth_h = {"Authorization": f"Bearer {access}", "Accept": "application/vnd.github+json"}
        user_res = client.get("https://api.github.com/user", headers=auth_h)
        if user_res.status_code >= 400:
            raise ValueError("GitHub profil alinamadi")
        user = user_res.json()

        email = (user.get("email") or "").strip()
        if not email:
            emails_res = client.get("https://api.github.com/user/emails", headers=auth_h)
            if emails_res.status_code < 400:
                emails = emails_res.json() or []
                primary = next(
                    (e for e in emails if e.get("primary") and e.get("verified")),
                    None,
                )
                verified = next((e for e in emails if e.get("verified")), None)
                chosen = primary or verified or (emails[0] if emails else None)
                if chosen:
                    email = (chosen.get("email") or "").strip()

    if not email:
        raise ValueError("GitHub hesabinda e-posta bulunamadi")
    subject = str(user.get("id") or "")
    if not subject:
        raise ValueError("GitHub kullanici id yok")
    name = (user.get("name") or user.get("login") or "").strip() or None
    return {
        "provider": "github",
        "subject": subject,
        "email": email,
        "name": name,
    }
