"""账户：注册、认证、登录、刷新与登出（JWT access + PG 持久化 refresh）。"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from configs.config import settings
from models.account import Account, AccountRefreshToken, AccountStatus
from services.errors.account import (
    AccountAlreadyExistsError,
    AccountLoginError,
    AccountPasswordError,
    AccountRefreshTokenError,
)


def naive_utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)


def compare_password(plain: str, stored_b64: str | None, salt_b64: str | None) -> bool:
    if not stored_b64 or not salt_b64:
        return False
    try:
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(stored_b64)
    except (ValueError, TypeError):
        return False
    digest = hash_password(plain, salt)
    return secrets.compare_digest(digest, expected)


def _hash_refresh_token(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    csrf_token: str


class AccountService:
    """账户服务：所有方法显式传入 ``db: Session``。"""

    @staticmethod
    def get_account_jwt_token(*, account: Account) -> str:
        expire = naive_utc_now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        payload: dict[str, Any] = {
            "sub": account.id,
            "exp": expire,
            "ver": int(account.access_token_version),
        }
        return jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )

    @staticmethod
    def decode_access_token(token: str) -> tuple[str, int]:
        """解析 access JWT，返回 ``(account_id, ver)``。缺少或非法 ``ver`` 时抛 ``jwt.InvalidTokenError``。"""
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        sub = payload.get("sub")
        if not isinstance(sub, str) or not sub:
            raise jwt.InvalidTokenError("missing sub")
        ver = payload.get("ver")
        if not isinstance(ver, int) or isinstance(ver, bool):
            raise jwt.InvalidTokenError("missing or invalid ver")
        return sub, ver

    @staticmethod
    def create_account(
        db: Session,
        *,
        email: str,
        password: str,
        name: str | None = None,
    ) -> Account:
        """注册新用户；邮箱存小写。"""
        normalized = email.strip().lower()
        if not normalized or not password:
            raise AccountPasswordError("邮箱或密码无效。")
        display_name = (name or normalized.split("@")[0]).strip() or normalized
        salt = secrets.token_bytes(16)
        b64_salt = base64.b64encode(salt).decode("ascii")
        pwd_hash = base64.b64encode(hash_password(password, salt)).decode("ascii")
        account = Account(
            name=display_name,
            email=normalized,
            password=pwd_hash,
            password_salt=b64_salt,
            status=AccountStatus.ACTIVE.value,
        )
        db.add(account)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise AccountAlreadyExistsError("该邮箱已注册。") from None
        db.refresh(account)
        return account

    @staticmethod
    def authenticate(
        db: Session,
        email: str,
        password: str,
        invite_token: str | None = None,
    ) -> Account:
        """邮箱密码认证；保留邀请场景下首次设置密码的逻辑。"""
        normalized = email.strip().lower()
        account = db.scalar(select(Account).where(Account.email == normalized).limit(1))
        if not account:
            raise AccountPasswordError("邮箱或密码错误。")

        if account.status == AccountStatus.BANNED.value:
            raise AccountLoginError("账户已封禁。")

        if password and invite_token and account.password is None:
            salt = secrets.token_bytes(16)
            base64_salt = base64.b64encode(salt).decode("ascii")
            password_hashed = base64.b64encode(hash_password(password, salt)).decode("ascii")
            account.password = password_hashed
            account.password_salt = base64_salt

        if account.password is None or not compare_password(password, account.password, account.password_salt):
            raise AccountPasswordError("邮箱或密码错误。")

        if account.status == AccountStatus.PENDING.value:
            account.status = AccountStatus.ACTIVE.value
            account.initialized_at = naive_utc_now()

        db.commit()
        db.refresh(account)
        return account

    @staticmethod
    def _generate_refresh_token_plain() -> str:
        return secrets.token_urlsafe(48)

    @staticmethod
    def _store_refresh_token(db: Session, *, account_id: str, plain: str) -> None:
        th = _hash_refresh_token(plain)
        expires_at = naive_utc_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        row = AccountRefreshToken(account_id=account_id, token_hash=th, expires_at=expires_at)
        db.add(row)
        db.commit()

    @staticmethod
    def login(
        db: Session,
        account: Account,
        *,
        ip_address: str | None = None,
    ) -> TokenPair:
        """签发 access / refresh；csrf 占位空串（纯 Bearer 场景不使用）。"""
        if ip_address:
            account.last_login_at = naive_utc_now()
            account.last_login_ip = ip_address
            db.add(account)
            db.commit()
            db.refresh(account)

        access_token = AccountService.get_account_jwt_token(account=account)
        refresh_plain = AccountService._generate_refresh_token_plain()
        AccountService._store_refresh_token(db, account_id=account.id, plain=refresh_plain)
        return TokenPair(access_token=access_token, refresh_token=refresh_plain, csrf_token="")

    @staticmethod
    def refresh_access_token(db: Session, refresh_token: str) -> TokenPair:
        """校验 refresh 并旋转存储行，返回新令牌对。"""
        th = _hash_refresh_token(refresh_token.strip())
        row = db.scalar(select(AccountRefreshToken).where(AccountRefreshToken.token_hash == th).limit(1))
        if row is None:
            raise AccountRefreshTokenError("Refresh 无效。")
        if row.expires_at < naive_utc_now():
            db.delete(row)
            db.commit()
            raise AccountRefreshTokenError("Refresh 已过期。")

        account = db.get(Account, row.account_id)
        if account is None or account.status == AccountStatus.BANNED.value:
            db.delete(row)
            db.commit()
            raise AccountRefreshTokenError("账户不可用。")

        db.delete(row)
        account.access_token_version = int(account.access_token_version) + 1
        db.add(account)
        db.commit()
        db.refresh(account)

        access_token = AccountService.get_account_jwt_token(account=account)
        refresh_plain = AccountService._generate_refresh_token_plain()
        AccountService._store_refresh_token(db, account_id=account.id, plain=refresh_plain)
        return TokenPair(access_token=access_token, refresh_token=refresh_plain, csrf_token="")

    @staticmethod
    def logout(db: Session, refresh_token: str) -> None:
        """撤销指定 refresh，并递增 access 版本使当前及旧 access JWT 失效。"""
        th = _hash_refresh_token(refresh_token.strip())
        row = db.scalar(select(AccountRefreshToken).where(AccountRefreshToken.token_hash == th).limit(1))
        if row is None:
            return
        account = db.get(Account, row.account_id)
        db.delete(row)
        if account is not None:
            account.access_token_version = int(account.access_token_version) + 1
            db.add(account)
        db.commit()

    @staticmethod
    def get_account_by_id(db: Session, account_id: str) -> Account | None:
        return db.get(Account, account_id)
