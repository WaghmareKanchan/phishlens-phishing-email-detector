"""Business rules for accounts, passwords and two-factor authentication."""
from __future__ import annotations

import hmac
from datetime import timedelta

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..core import security
from ..core.exceptions import AppError
from ..core.rate_limit import forgot_limiter, login_limiter, register_limiter, reset_limiter, twofa_limiter
from ..models import PasswordReset, User, utcnow
from ..schemas import auth as s
from . import mail_service

BAD_LOGIN = "The email or password is not correct."


# ───────────────────────── register / login ─────────────────────────
def register(db: Session, payload: s.RegisterIn, ip: str) -> tuple[str, User]:
    register_limiter.check(ip)
    register_limiter.hit(ip)
    cfg = get_settings()
    email = payload.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise AppError(409, "An account with this email already exists.", code="email_taken")

    is_first = db.query(User).count() == 0
    user = User(name=payload.name, email=email,
                password_hash=security.hash_password(payload.password),
                is_admin=(cfg.first_user_is_admin and is_first) or email in cfg.admin_email_list)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:   # two people registered the same e-mail at the same instant
        db.rollback()
        raise AppError(409, "An account with this email already exists.", code="email_taken")
    return security.create_access_token(user.id, user.token_version), user


def login(db: Session, payload: s.LoginIn, ip: str) -> s.LoginResult:
    email = payload.email.lower()
    key = f"{ip}|{email}"
    login_limiter.check(key)

    user = db.query(User).filter(User.email == email).first()
    if not user:
        security.burn_password_check(payload.password)   # same timing as a real check
        login_limiter.hit(key)
        raise AppError(401, BAD_LOGIN, code="bad_credentials")
    if not security.verify_password(payload.password, user.password_hash):
        login_limiter.hit(key)
        raise AppError(401, BAD_LOGIN, code="bad_credentials")
    login_limiter.reset(key)

    if user.two_factor_enabled:
        return s.LoginResult(two_factor_required=True, temp_token=security.create_temp_token(user.id))
    # 2FA is not on yet: log them in, but tell the client to ask them to set it up. They may skip it,
    # but they are asked again at EVERY login until they finish the setup.
    return s.LoginResult(two_factor_required=False, two_factor_setup_required=True,
                         access_token=security.create_access_token(user.id, user.token_version),
                         user=s.UserOut.model_validate(user))


# ───────────────────────── second factor helpers ─────────────────────────
def _consume_totp_step(db: Session, user: User, step: int) -> bool:
    """Atomically remember `step` as used. False if a parallel request already used it (replay)."""
    res = db.execute(update(User).where(User.id == user.id, User.totp_last_step < step)
                     .values(totp_last_step=step))
    db.commit()
    if res.rowcount == 1:
        user.totp_last_step = step
        return True
    return False


def _check_second_factor(db: Session, user: User, code: str) -> bool:
    """Accepts a live authenticator (TOTP) code and consumes its time step so it cannot be replayed."""
    step = security.verify_totp(user.totp_secret, code, user.totp_last_step)
    return step is not None and _consume_totp_step(db, user, step)


def verify_login_2fa(db: Session, payload: s.TwoFactorVerifyIn) -> tuple[str, User]:
    claims = security.decode_token(payload.temp_token, expected_scope="2fa_pending")
    if not claims:
        raise AppError(401, "This login attempt has expired. Log in again.", code="login_expired")
    user = db.get(User, claims["sub"])
    if not user or not user.two_factor_enabled:
        raise AppError(401, "This login attempt is no longer valid.", code="login_expired")

    twofa_limiter.check(user.id)
    if _check_second_factor(db, user, payload.code):
        twofa_limiter.reset(user.id)
        return security.create_access_token(user.id, user.token_version), user
    twofa_limiter.hit(user.id)
    raise AppError(401, "That code is not correct, expired, or already used.", code="bad_code")


# ───────────────────────── password ─────────────────────────
def change_password(db: Session, user: User, payload: s.ChangePasswordIn) -> str:
    twofa_limiter.check("pw:" + user.id)
    if not security.verify_password(payload.current_password, user.password_hash):
        twofa_limiter.hit("pw:" + user.id)
        raise AppError(400, "That is not your current password.", code="wrong_password")
    user.password_hash = security.hash_password(payload.new_password)
    user.token_version += 1          # signs out every other device
    db.commit()
    return security.create_access_token(user.id, user.token_version)


def forgot_password(db: Session, email_in: str) -> s.ForgotOut:
    cfg = get_settings()
    email = email_in.lower()
    generic = f"If an account exists for {email}, a reset code is on its way."
    try:
        forgot_limiter.check(email)
    except AppError:
        return s.ForgotOut(message=generic)   # same answer: do not reveal that we throttled
    forgot_limiter.hit(email)

    user = db.query(User).filter(User.email == email).first()
    if not user:
        return s.ForgotOut(message=generic)

    db.query(PasswordReset).filter_by(user_id=user.id).delete()
    code = security.generate_reset_code()
    db.add(PasswordReset(user_id=user.id, code_hash=security.hash_reset_code(email, code),
                         expires_at=utcnow() + timedelta(minutes=cfg.reset_code_ttl_minutes)))
    db.commit()
    sent = mail_service.send_reset_code(user.email, code)
    dev_code = code if (not cfg.is_production and not sent) else None
    return s.ForgotOut(message=generic, dev_code=dev_code)


def reset_password(db: Session, payload: s.ResetIn) -> None:
    cfg = get_settings()
    email = payload.email.lower()
    reset_limiter.check(email)
    invalid = AppError(400, "That code is not valid. Request a new code and try again.", code="bad_reset_code")

    user = db.query(User).filter(User.email == email).first()
    pr = (db.query(PasswordReset).filter_by(user_id=user.id)
          .order_by(PasswordReset.created_at.desc()).first()) if user else None
    if not user or not pr:
        reset_limiter.hit(email)
        raise invalid
    if pr.expires_at < utcnow():
        db.delete(pr)
        db.commit()
        raise AppError(400, "This code has expired. Request a new code and try again.", code="reset_expired")

    if not hmac.compare_digest(pr.code_hash, security.hash_reset_code(email, payload.code)):
        pr.attempts += 1
        reset_limiter.hit(email)
        left = cfg.reset_max_attempts - pr.attempts
        if left <= 0:
            db.delete(pr)
            db.commit()
            raise AppError(400, "Too many wrong codes. Request a new code and try again.", code="reset_locked")
        db.commit()
        raise AppError(400, f"That code is not correct. {left} tries left.", code="bad_reset_code")

    user.password_hash = security.hash_password(payload.new_password)
    user.token_version += 1
    db.query(PasswordReset).filter_by(user_id=user.id).delete()
    db.commit()
    reset_limiter.reset(email)


# ───────────────────────── 2FA management ─────────────────────────
# Once 2FA is on it stays on: there is deliberately no "disable" operation, and no backup codes
# are generated or stored. The only thing kept in the database is the TOTP secret.
def setup_2fa(db: Session, user: User) -> s.TotpSetupOut:
    if user.two_factor_enabled:
        raise AppError(409, "Two-factor authentication is already on.", code="2fa_already_on")
    secret = security.generate_totp_secret()
    user.totp_secret = secret        # inactive until /2fa/confirm succeeds
    user.totp_last_step = 0
    db.commit()
    uri = security.totp_otpauth_uri(secret, user.email)
    return s.TotpSetupOut(otpauth_uri=uri, qr_svg=security.totp_qr_svg(uri))


def confirm_2fa(db: Session, user: User, code: str) -> None:
    if user.two_factor_enabled:
        raise AppError(409, "Two-factor authentication is already on.", code="2fa_already_on")
    if not user.totp_secret:
        raise AppError(400, "Start setup first.", code="2fa_not_started")
    twofa_limiter.check(user.id)
    step = security.verify_totp(user.totp_secret, code, 0)
    if step is None:
        twofa_limiter.hit(user.id)
        raise AppError(400, "That code is not correct. Check the app and try again.", code="bad_code")
    user.two_factor_enabled = True
    user.totp_last_step = step
    db.commit()
