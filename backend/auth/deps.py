"""FastAPI auth dependencies."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.auth.jwt import decode_access_token
from modules.auth import get_user_by_id
from modules.repo_sessions import get_session

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> dict:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kimlik dogrulama gerekli",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload.get("sub", 0))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gecersiz veya suresi dolmus token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_id(user_id)
    if not user or not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanici bulunamadi veya deaktif",
        )
    return user


CurrentUser = Annotated[dict, Depends(get_current_user)]


def get_current_session(
    user: CurrentUser,
    x_session_id: Annotated[str | None, Header(alias="X-Session-Id")] = None,
) -> dict:
    if not x_session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Session-Id basligi gerekli",
        )
    try:
        sid = int(x_session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Gecersiz oturum id")
    sess = get_session(sid, user_id=user["id"])
    if not sess:
        raise HTTPException(status_code=404, detail="Oturum bulunamadi")
    return sess


CurrentSession = Annotated[dict, Depends(get_current_session)]
