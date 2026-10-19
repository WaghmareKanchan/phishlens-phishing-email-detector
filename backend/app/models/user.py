from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..database import Base
from .types import UTCDateTime, new_id, utcnow


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=new_id)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)

    # Bumped on password change / reset: every JWT carries the value it was issued with, so old
    # tokens (other devices, a thief's copy) stop working immediately.
    token_version = Column(Integer, default=0, nullable=False)

    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    totp_secret = Column(String, nullable=True)       # only meaningful once two_factor_enabled
    totp_last_step = Column(Integer, default=0, nullable=False)  # replay protection

    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(UTCDateTime, default=utcnow, nullable=False)

    emails = relationship("Email", back_populates="owner", cascade="all, delete-orphan")
    analyses = relationship("Analysis", back_populates="user", cascade="all, delete-orphan")
    reset_tokens = relationship("PasswordReset", back_populates="user", cascade="all, delete-orphan")


class PasswordReset(Base):
    """A 6-digit "forgot password" code (hashed, expiring, limited attempts). One active per user."""
    __tablename__ = "password_resets"

    id = Column(String, primary_key=True, default=new_id)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    code_hash = Column(String, nullable=False)
    expires_at = Column(UTCDateTime, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    created_at = Column(UTCDateTime, default=utcnow, nullable=False)

    user = relationship("User", back_populates="reset_tokens")
