"""账户 ORM：与 core.user_context 的 user_id（字符串）对齐，主键为 UUID 字符串。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class AccountStatus(str, Enum):
    """账户状态。"""

    ACTIVE = "active"
    PENDING = "pending"
    BANNED = "banned"


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = {
        "comment": "用户账户：邮箱登录、密码盐与状态",
        "extend_existing": True,
    }

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        insert_default=lambda: str(uuid4()),
        comment="主键 UUID 字符串",
    )
    name: Mapped[str] = mapped_column(String(255), comment="显示名")
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, comment="邮箱，唯一小写存储")
    password: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="密码哈希（base64）")
    password_salt: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="盐（base64）")
    avatar: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="头像 URL")
    interface_language: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="界面语言")
    interface_theme: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="界面主题")
    timezone: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="时区")
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最近登录时间"
    )
    last_login_ip: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="最近登录 IP")
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="最近活跃时间",
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default="active",
        default=AccountStatus.ACTIVE.value,
        comment="active / pending / banned",
    )
    initialized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="首次激活时间"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )
    # 刷新 / 登出时递增；JWT 内携带 ver，须与库中一致才有效，用于作废旧 access
    access_token_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        default=0,
        comment="access 令牌版本，刷新或登出后递增",
    )

    refresh_tokens: Mapped[list["AccountRefreshToken"]] = relationship(
        "AccountRefreshToken",
        back_populates="account",
        cascade="all, delete-orphan",
    )

    @property
    def is_password_set(self) -> bool:
        return self.password is not None


class AccountRefreshToken(Base):
    """Refresh 令牌持久化：仅存哈希，明文仅签发时返回一次。"""

    __tablename__ = "account_refresh_tokens"
    __table_args__ = (
        Index("ix_account_refresh_token_hash", "token_hash", unique=True),
        Index("ix_account_refresh_account_id", "account_id"),
        {
            "comment": "账户 refresh 令牌：哈希、过期时间",
            "extend_existing": True,
        },
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="主键"
    )
    account_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        comment="账户 ID",
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, comment="SHA256 十六进制")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="过期时间")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )

    account: Mapped["Account"] = relationship("Account", back_populates="refresh_tokens")
