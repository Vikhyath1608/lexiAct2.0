from __future__ import annotations
from typing import Optional, Union
from pydantic import BaseModel, field_validator


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    full_name: str = ""


class VerifyOTPRequest(BaseModel):
    user_id: Union[int, str]
    otp: str

    @field_validator("user_id", mode="before")
    @classmethod
    def coerce_user_id(cls, v):
        try:
            return int(v)
        except (ValueError, TypeError):
            raise ValueError("user_id must be an integer")


class ResendOTPRequest(BaseModel):
    email: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    full_name: str
    user_id: int


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserPublic(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    is_active: bool
    oauth_provider: Optional[str] = None
    model_config = {"from_attributes": True}