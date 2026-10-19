"""Security primitives: password hashing, JWTs, TOTP 2FA, password-reset codes.

Everything here is pure (no DB access) so it is easy to unit-test.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import pyotp
from jose import JWTError, jwt

from ..config import get_secret_key, get_settings

ALGORITHM = "HS256"


# ───────────────────────── passwords ─────────────────────────
def _prehash(password: str) -> bytes:
    """bcrypt only looks at the first 72 BYTES of its input and silently ignores the rest
    (two long passwords that share a prefix would be "equal"). Hashing first with SHA-256 and
    base64-encoding gives a fixed 44-byte input, so the whole password always counts."""
    return base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())


def hash_password(password: str) -> str:
    rounds = get_settings().bcrypt_rounds
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt(rounds=rounds)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(password), password_hash.encode("ascii"))
    except (ValueError, TypeError):
        return False


_dummy_hash: Optional[str] = None


def burn_password_check(password: str) -> None:
    """Do the same amount of work as a real check, for unknown e-mails, so response time does
    not reveal which e-mail addresses have accounts."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("not-a-real-password")
    verify_password(password, _dummy_hash)


# ───────────────────────── JWT ─────────────────────────
def create_token(subject: str, scope: str, expires_minutes: int, **claims) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "scope": scope, "iat": now,
               "exp": now + timedelta(minutes=expires_minutes), **claims}
    return jwt.encode(payload, get_secret_key(), algorithm=ALGORITHM)


def create_access_token(user_id: str, token_version: int) -> str:
    return create_token(user_id, "access", get_settings().access_token_expire_minutes, tv=token_version)


def create_temp_token(user_id: str) -> str:
    """Issued after a correct password but BEFORE the 2FA code. Scoped so it can only be used on
    /auth/2fa/verify, and short-lived."""
    return create_token(user_id, "2fa_pending", get_settings().temp_token_expire_minutes)


def decode_token(token: str, expected_scope: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, get_secret_key(), algorithms=[ALGORITHM])
    except JWTError:
        return None
    if payload.get("scope") != expected_scope or not payload.get("sub"):
        return None
    return payload


# ───────────────────────── keyed hashes for short codes ─────────────────────────
def keyed_hash(value: str) -> str:
    """HMAC-SHA256 with the server secret. Reset codes are short, so a plain
    hash could be brute-forced offline if the DB leaked; the secret key prevents that."""
    return hmac.new(get_secret_key().encode(), value.encode(), hashlib.sha256).hexdigest()


# ───────────────────────── TOTP (RFC 6238) ─────────────────────────
TOTP_STEP = 30


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def totp_otpauth_uri(secret: str, email: str, issuer: str = "PhishLens") -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def totp_qr_svg(otpauth_uri: str) -> str:
    """The QR code as a scalable inline SVG, drawn on the server (no CDN script needed in the browser).

    It has a viewBox (so it scales to any box without being cut off) and the standard 4-module white
    border (the "quiet zone" scanners need). The secret itself is never shown as text."""
    import segno
    qr = segno.make(otpauth_uri, error="m")
    border = 4
    size = len(qr.matrix) + 2 * border
    parts = []
    for y, row in enumerate(qr.matrix):
        x = 0
        while x < len(row):
            if row[x]:
                start = x
                while x < len(row) and row[x]:
                    x += 1
                parts.append(f"M{start + border} {y + border}h{x - start}v1h-{x - start}z")
            else:
                x += 1
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" shape-rendering="crispEdges" '
            f'role="img" aria-label="QR code for your authenticator app">'
            f'<rect width="{size}" height="{size}" fill="#ffffff"/><path fill="#000000" d="{"".join(parts)}"/></svg>')


def verify_totp(secret: Optional[str], code: str, last_used_step: int = 0) -> Optional[int]:
    """Return the matching 30-second time-step, or None.

    * ±1 step of tolerance for clock drift between phone and server.
    * A step <= last_used_step is rejected, so a code that was already accepted (or shoulder-
      surfed) cannot be replayed inside its validity window.
    """
    if not secret:
        return None
    code = re.sub(r"\s+", "", code or "")
    if not re.fullmatch(r"\d{6}", code):
        return None
    totp = pyotp.TOTP(secret)
    now_step = int(time.time() // TOTP_STEP)
    for step in (now_step - 1, now_step, now_step + 1):
        if hmac.compare_digest(totp.at(step * TOTP_STEP), code) and step > last_used_step:
            return step
    return None


# ───────────────────────── password-reset codes ─────────────────────────
def generate_reset_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_reset_code(email: str, code: str) -> str:
    return keyed_hash(f"reset:{email.lower()}:{code}")
