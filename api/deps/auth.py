"""认证依赖：解析 Bearer access，校验账户并绑定 ``user_context``。"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from core import user_context
from db import get_db
from models.account import Account, AccountStatus
from services.account_service import AccountService

# auto_error=False：缺失 Authorization 时由本依赖返回 401，而非框架默认错误体
security = HTTPBearer(auto_error=False)


async def get_current_account_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Session = Depends(get_db),
) -> AsyncGenerator[str, None]:
    """已登录则 ``yield`` 当前 ``account_id``，并在请求结束时复位 ``ContextVar``。"""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登录或令牌缺失")
    try:
        account_id, token_ver = AccountService.decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "令牌无效或已过期") from None

    account = AccountService.get_account_by_id(db, account_id)
    if account is None or account.status == AccountStatus.BANNED.value:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "账户不可用")
    if int(account.access_token_version) != token_ver:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "令牌已失效，请使用新 access 或重新登录")

    reset_token = user_context.set_user_id(account.id)
    try:
        yield account.id
    finally:
        user_context.current_user_id.reset(reset_token)


async def get_current_account(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Session = Depends(get_db),
) -> AsyncGenerator[Account, None]:
    """已登录则 ``yield`` ORM ``Account``，并在请求结束时复位 ``ContextVar``。"""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登录或令牌缺失")
    try:
        account_id, token_ver = AccountService.decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "令牌无效或已过期") from None

    account = AccountService.get_account_by_id(db, account_id)
    if account is None or account.status == AccountStatus.BANNED.value:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "账户不可用")
    if int(account.access_token_version) != token_ver:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "令牌已失效，请使用新 access 或重新登录")

    reset_token = user_context.set_user_id(account.id)
    try:
        yield account
    finally:
        user_context.current_user_id.reset(reset_token)
