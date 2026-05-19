"""认证路由：注册、登录、刷新、登出、当前用户。"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from db import get_db
from deps.auth import get_current_account
from models.account import Account
from schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MeResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from services.account_service import AccountService
from services.errors.account import (
    AccountAlreadyExistsError,
    AccountLoginError,
    AccountPasswordError,
    AccountRefreshTokenError,
)


router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    if request.client:
        return request.client.host
    return None


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    """注册并返回令牌（与登录后一致）。"""
    try:
        account = AccountService.create_account(
            db,
            email=str(payload.email),
            password=payload.password,
            name=payload.name,
        )
    except AccountAlreadyExistsError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e)) from e
    except AccountPasswordError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    pair = AccountService.login(db, account, ip_address=_client_ip(request))
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        csrf_token=pair.csrf_token,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    """邮箱密码登录。"""
    try:
        account = AccountService.authenticate(
            db,
            str(payload.email),
            payload.password,
            invite_token=payload.invite_token,
        )
    except AccountLoginError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except AccountPasswordError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e
    pair = AccountService.login(db, account, ip_address=_client_ip(request))
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        csrf_token=pair.csrf_token,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """使用 refresh 换取新的 access + refresh（旋转存储）。"""
    try:
        pair = AccountService.refresh_access_token(db, payload.refresh_token)
    except AccountRefreshTokenError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        csrf_token=pair.csrf_token,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: LogoutRequest, db: Session = Depends(get_db)) -> None:
    """撤销 body 中的 refresh（幂等：不存在也返回 204）。"""
    AccountService.logout(db, payload.refresh_token)


@router.get("/me", response_model=MeResponse)
def me(account: Account = Depends(get_current_account)) -> MeResponse:
    """校验 access token 并返回当前用户摘要。"""
    return MeResponse(id=account.id, email=account.email, name=account.name, status=account.status)
