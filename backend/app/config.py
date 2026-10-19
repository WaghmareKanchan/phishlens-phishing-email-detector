"""Central configuration. Everything comes from environment variables / backend/.env."""
from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    env: str = "development"
    secret_key: str = ""
    # Absolute path so the DB does not depend on the directory you start the server from.
    database_url: str = f"sqlite:///{BACKEND_DIR / 'phishlens.db'}"
    cors_origins: str = ""

    access_token_expire_minutes: int = 60 * 24
    temp_token_expire_minutes: int = 5
    bcrypt_rounds: int = 12

    first_user_is_admin: bool = True
    admin_emails: str = ""

    reset_code_ttl_minutes: int = 10
    reset_max_attempts: int = 5

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "PhishLens <no-reply@example.com>"

    artifacts_dir: Path = BACKEND_DIR / "artifacts"
    frontend_dir: Path = PROJECT_DIR / "frontend"

    # CSV uploads have NO size limit. max_batch_rows is an optional safety cap on the number of
    # e-mails scanned per upload; 0 (the default) means "scan every row".
    max_batch_rows: int = 0

    # ---- convenience views of the raw strings above ----
    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def admin_email_list(self) -> List[str]:
        return [e.strip().lower() for e in self.admin_emails.split(",") if e.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_secret_key() -> str:
    """Return the JWT/HMAC signing key.

    Production: SECRET_KEY must be set, otherwise we refuse to start (a random per-process key
    would silently log everybody out on every restart and break password-reset codes).
    Development: a random key is generated once and stored in backend/.dev_secret_key so
    restarting the dev server does not invalidate your session.
    """
    s = get_settings()
    if s.secret_key:
        return s.secret_key
    if s.is_production:
        raise RuntimeError("SECRET_KEY must be set when ENV=production.")
    path = BACKEND_DIR / ".dev_secret_key"
    try:
        if path.exists():
            return path.read_text().strip()
        key = secrets.token_hex(32)
        path.write_text(key)
        return key
    except OSError:
        return secrets.token_hex(32)
