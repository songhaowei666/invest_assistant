"""认证相关请求/响应模型。"""

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)
    name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)
    invite_token: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    csrf_token: str = ""


class MeResponse(BaseModel):
    id: str
    email: str
    name: str
    status: str
