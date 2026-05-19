"""Auth dependency。M0-M2 走 mock（讀 X-User-Id）；sso 模式待補 OIDC。"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.models.db import User

MOCK_DEFAULT_USER = "dev-bu-001"


def current_user(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    user_id_qs: str | None = Query(default=None, alias="user_id"),
    db: Session = Depends(get_db),
) -> User:
    """Auth dependency.

    Priority: Header `X-User-Id` > query `?user_id=` > default.
    Query 備援僅在 mock mode 啟用，專門給瀏覽器原生 EventSource 使用
    （EventSource API 無法自訂 header）。
    """
    if settings.auth_mode == "mock":
        user_id = x_user_id or user_id_qs or MOCK_DEFAULT_USER
    else:  # sso：M1 尚未實作；先拒絕以免誤用
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="SSO auth not yet implemented",
        )

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"unknown user {user_id}",
        )
    return user
