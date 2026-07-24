"""Auth routes."""

from fastapi import APIRouter, HTTPException, status

from backend.auth.deps import CurrentUser
from backend.auth.jwt import create_access_token
from backend.llm import FAST_MODEL, QUALITY_MODEL, default_model_name
from backend.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from modules.auth import login, register, update_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def auth_register(body: RegisterRequest):
    try:
        user_id = register(body.email, body.password, body.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if user_id is None:
        raise HTTPException(status_code=400, detail="Bu email zaten kayitli")

    user = {"id": user_id, "email": body.email.lower().strip(), "name": body.name.strip()}
    token = create_access_token(user_id, user["email"])
    return TokenResponse(access_token=token, user=UserOut(**user))


@router.post("/login", response_model=TokenResponse)
def auth_login(body: LoginRequest):
    user = login(body.email, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email veya sifre hatali",
        )
    token = create_access_token(user["id"], user["email"])
    return TokenResponse(access_token=token, user=UserOut(**user))


@router.get("/me", response_model=UserOut)
def auth_me(user: CurrentUser):
    return UserOut(id=user["id"], email=user["email"], name=user.get("name"))


@router.post("/change-password")
def auth_change_password(body: ChangePasswordRequest, user: CurrentUser):
    ok = update_password(user["id"], body.old_password, body.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail="Sifre guncellenemedi")
    return {"ok": True}


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
