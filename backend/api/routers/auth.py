"""Auth routes."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse

from backend.auth.deps import CurrentUser
from backend.auth.jwt import create_access_token
from backend.config import get_settings
from backend.llm import FAST_MODEL, QUALITY_MODEL, default_model_name
from backend.schemas import (
    AvatarIconRequest,
    ChangePasswordRequest,
    ConfirmEmailChangeRequest,
    ConfirmPasswordChangeRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    ResetPasswordVerifyRequest,
    SecurityCodeRequest,
    SecurityCodeVerifyRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserOut,
)
from backend.services import oauth as oauth_svc
from modules.auth import (
    get_user_by_id,
    login,
    register,
    set_avatar,
    update_profile,
    upsert_oauth_user,
)
from modules.security_codes import (
    confirm_email_change,
    confirm_password_change,
    confirm_password_reset,
    request_password_reset,
    request_security_code,
    verify_password_reset,
    verify_security_code,
)

router = APIRouter(prefix="/auth", tags=["auth"])

ALLOWED_AVATAR_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_AVATAR_BYTES = 2 * 1024 * 1024
ALLOWED_ICONS = {
    "person",
    "face",
    "school",
    "psychology",
    "menu_book",
    "lightbulb",
    "science",
    "biotech",
    "pets",
    "favorite",
    "star",
    "bolt",
    "palette",
    "music_note",
    "sports_esports",
    "travel_explore",
}


def _user_out(user: dict) -> UserOut:
    return UserOut(
        id=user["id"],
        email=user["email"],
        name=user.get("name"),
        username=user.get("username"),
        avatar_type=user.get("avatar_type") or "default",
        avatar_value=user.get("avatar_value"),
    )


def _avatars_dir() -> Path:
    root = Path(get_settings().uploads_root) / "avatars"
    root.mkdir(parents=True, exist_ok=True)
    return root


@router.post("/register", response_model=TokenResponse)
def auth_register(body: RegisterRequest):
    try:
        user_id = register(body.email, body.password, body.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if user_id is None:
        raise HTTPException(status_code=400, detail="Bu email zaten kayitli")

    user = get_user_by_id(user_id) or {
        "id": user_id,
        "email": body.email.lower().strip(),
        "name": body.name.strip(),
    }
    token = create_access_token(user_id, user["email"])
    return TokenResponse(access_token=token, user=_user_out(user))


@router.post("/login", response_model=TokenResponse)
def auth_login(body: LoginRequest):
    user = login(body.email, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email veya sifre hatali",
        )
    token = create_access_token(user["id"], user["email"])
    return TokenResponse(access_token=token, user=_user_out(user))


@router.get("/oauth/providers")
def auth_oauth_providers():
    return {"providers": oauth_svc.configured_providers()}


@router.get("/oauth/{provider}/start")
def auth_oauth_start(provider: str, request: Request):
    provider = provider.lower().strip()
    if provider not in oauth_svc.PROVIDERS:
        raise HTTPException(status_code=404, detail="Bilinmeyen OAuth saglayici")
    base = oauth_svc.oauth_base_url(str(request.base_url).rstrip("/"))
    try:
        url, _state = oauth_svc.authorization_url(provider, base_url=base)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(url=url, status_code=302)


@router.get("/oauth/{provider}/callback")
def auth_oauth_callback(
    provider: str,
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    provider = provider.lower().strip()
    base = oauth_svc.oauth_base_url(str(request.base_url).rstrip("/"))
    if error:
        msg = error_description or error
        return RedirectResponse(
            url=f"/?login=1&oauth_error={msg}",
            status_code=302,
        )
    if not code or not state:
        return RedirectResponse(url="/?login=1&oauth_error=Eksik+OAuth+yaniti", status_code=302)
    try:
        profile = oauth_svc.exchange_code(
            provider, code=code, state=state, base_url=base
        )
        user = upsert_oauth_user(
            provider=profile["provider"],
            subject=profile["subject"],
            email=profile["email"],
            name=profile.get("name"),
        )
        token = create_access_token(user["id"], user["email"])
    except ValueError as e:
        from urllib.parse import quote

        return RedirectResponse(
            url=f"/?login=1&oauth_error={quote(str(e))}",
            status_code=302,
        )

    from urllib.parse import quote

    return RedirectResponse(
        url=f"/oturumlar?oauth_token={quote(token)}",
        status_code=302,
    )


@router.get("/me", response_model=UserOut)
def auth_me(user: CurrentUser):
    fresh = get_user_by_id(user["id"]) or user
    return _user_out(fresh)


@router.patch("/profile", response_model=UserOut)
def auth_update_profile(body: UpdateProfileRequest, user: CurrentUser):
    try:
        updated = update_profile(
            user["id"],
            name=body.name,
            username=body.username,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _user_out(updated)


@router.post("/security/request-code")
def auth_request_security_code(body: SecurityCodeRequest, user: CurrentUser):
    try:
        return request_security_code(user_id=user["id"], purpose=body.purpose.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/security/verify-code")
def auth_verify_security_code(body: SecurityCodeVerifyRequest, user: CurrentUser):
    try:
        return verify_security_code(
            user_id=user["id"],
            purpose=body.purpose.strip(),
            code=body.code.strip(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/security/confirm-email", response_model=TokenResponse)
def auth_confirm_email_change(body: ConfirmEmailChangeRequest, user: CurrentUser):
    try:
        updated = confirm_email_change(
            user_id=user["id"],
            code=body.code.strip(),
            new_email=body.new_email,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    token = create_access_token(updated["id"], updated["email"])
    return TokenResponse(access_token=token, user=_user_out(updated))


@router.post("/security/confirm-password")
def auth_confirm_password_change(body: ConfirmPasswordChangeRequest, user: CurrentUser):
    try:
        confirm_password_change(
            user_id=user["id"],
            code=body.code.strip(),
            new_password=body.new_password,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.post("/forgot-password")
def auth_forgot_password(body: ForgotPasswordRequest, request: Request):
    """Send password-reset activation code to the account email (by email or username)."""
    base = str(request.base_url).rstrip("/")
    reset_url = f"{base}/sifre-sifirla"
    try:
        return request_password_reset(
            identifier=body.identifier.strip(),
            reset_url=reset_url,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/reset-password/verify")
def auth_reset_password_verify(body: ResetPasswordVerifyRequest):
    try:
        return verify_password_reset(
            identifier=body.identifier.strip(),
            code=body.code.strip(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reset-password")
def auth_reset_password(body: ResetPasswordRequest):
    try:
        confirm_password_reset(
            identifier=body.identifier.strip(),
            code=body.code.strip(),
            new_password=body.new_password,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "message": "Sifre guncellendi"}


@router.post("/change-password")
def auth_change_password(body: ChangePasswordRequest, user: CurrentUser):
    raise HTTPException(
        status_code=400,
        detail="Sifre degisikligi aktivasyon kodu ile yapilir (/auth/security/...)",
    )


@router.post("/avatar", response_model=UserOut)
async def auth_upload_avatar(user: CurrentUser, file: UploadFile = File(...)):
    filename = file.filename or "avatar.png"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_AVATAR_EXT:
        raise HTTPException(status_code=400, detail="Sadece jpg, png, webp, gif yuklenebilir")
    data = await file.read()
    if len(data) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=400, detail="Dosya en fazla 2 MB olabilir")
    if not data:
        raise HTTPException(status_code=400, detail="Bos dosya")

    stored = f"u{user['id']}_{uuid.uuid4().hex[:8]}{ext}"
    path = _avatars_dir() / stored
    # Eski dosyayi temizle
    prev = get_user_by_id(user["id"])
    if prev and prev.get("avatar_type") == "image" and prev.get("avatar_value"):
        old = _avatars_dir() / prev["avatar_value"]
        if old.is_file():
            try:
                old.unlink()
            except OSError:
                pass
    path.write_bytes(data)
    try:
        updated = set_avatar(user["id"], "image", stored)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _user_out(updated)


@router.post("/avatar/icon", response_model=UserOut)
def auth_set_avatar_icon(body: AvatarIconRequest, user: CurrentUser):
    icon = body.icon.strip()
    if icon not in ALLOWED_ICONS:
        raise HTTPException(status_code=400, detail="Gecersiz ikon")
    try:
        updated = set_avatar(user["id"], "icon", icon)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _user_out(updated)


@router.delete("/avatar", response_model=UserOut)
def auth_clear_avatar(user: CurrentUser):
    prev = get_user_by_id(user["id"])
    if prev and prev.get("avatar_type") == "image" and prev.get("avatar_value"):
        old = _avatars_dir() / prev["avatar_value"]
        if old.is_file():
            try:
                old.unlink()
            except OSError:
                pass
    try:
        updated = set_avatar(user["id"], "default", None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _user_out(updated)


@router.get("/avatar-icons")
def auth_avatar_icons():
    return {"icons": sorted(ALLOWED_ICONS)}


@router.get("/models")
def list_models():
    return {
        "default": default_model_name(),
        "provider": "groq",
        "models": [
            {"id": QUALITY_MODEL, "label": "Llama 3.3 70B (kalite)"},
            {"id": FAST_MODEL, "label": "Llama 3.1 8B (hizli)"},
        ],
    }
