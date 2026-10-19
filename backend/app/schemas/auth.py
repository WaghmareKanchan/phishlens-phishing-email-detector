import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _check_password_strength(v: str) -> str:
    if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
        raise ValueError("Use at least 6 characters, including a letter and a number.")
    return v


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=200)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Enter your full name.")
        return v

    _pw = field_validator("password")(_check_password_strength)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    email: str
    two_factor_enabled: bool
    is_admin: bool
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    user: UserOut


class LoginResult(BaseModel):
    """If two_factor_required is true the client must call /auth/2fa/verify with the temp_token."""
    two_factor_required: bool
    two_factor_setup_required: bool = False   # logged in, but 2FA is not on yet -> client asks them to set it up
    access_token: Optional[str] = None
    temp_token: Optional[str] = None
    user: Optional[UserOut] = None


class TwoFactorVerifyIn(BaseModel):
    temp_token: str
    code: str = Field(min_length=1, max_length=12)   # 6-digit authenticator code


class CodeIn(BaseModel):
    code: str = Field(min_length=1, max_length=12)


class TotpSetupOut(BaseModel):
    otpauth_uri: str      # the QR code content; the raw secret is never sent as a separate field
    qr_svg: str           # the same QR code, already drawn as SVG by the server


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=6, max_length=200)

    _pw = field_validator("new_password")(_check_password_strength)


class ChangePasswordOut(BaseModel):
    ok: bool = True
    access_token: str   # fresh token: the old one (and every other device) is now invalid


class ForgotIn(BaseModel):
    email: EmailStr


class ForgotOut(BaseModel):
    message: str
    dev_code: Optional[str] = None   # ONLY filled in development when no SMTP server is configured


class ResetIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=6, max_length=200)

    _pw = field_validator("new_password")(_check_password_strength)


class OkOut(BaseModel):
    ok: bool = True
