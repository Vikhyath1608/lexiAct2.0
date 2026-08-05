"""app/schemas/auth.py"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str = Field(default="", max_length=128)


class VerifyOTPRequest(BaseModel):
    user_id: int
    otp: str = Field(..., min_length=6, max_length=6)


class ResendOTPRequest(BaseModel):
    email: EmailStr


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    full_name: str
    user_id: int


class RefreshRequest(BaseModel):
    """Used when refresh token is sent in body (alternative to cookie)."""
    refresh_token: Optional[str] = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)


class UserPublic(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    is_active: bool
    oauth_provider: Optional[str] = None

    model_config = {"from_attributes": True}
