from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..core.deps import client_ip, get_current_user
from ..database import get_db
from ..models import User
from ..schemas import auth as s
from ..services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=s.TokenOut, status_code=201)
def register(payload: s.RegisterIn, request: Request, db: Session = Depends(get_db)):
    token, user = auth_service.register(db, payload, client_ip(request))
    return s.TokenOut(access_token=token, user=s.UserOut.model_validate(user))


@router.post("/login", response_model=s.LoginResult)
def login(payload: s.LoginIn, request: Request, db: Session = Depends(get_db)):
    return auth_service.login(db, payload, client_ip(request))


@router.post("/2fa/verify", response_model=s.TokenOut)
def verify_2fa_login(payload: s.TwoFactorVerifyIn, db: Session = Depends(get_db)):
    """Completes a login that /auth/login flagged as two_factor_required (authenticator code)."""
    token, user = auth_service.verify_login_2fa(db, payload)
    return s.TokenOut(access_token=token, user=s.UserOut.model_validate(user))


@router.get("/me", response_model=s.UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/change-password", response_model=s.ChangePasswordOut)
def change_password(payload: s.ChangePasswordIn, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    return s.ChangePasswordOut(access_token=auth_service.change_password(db, user, payload))


@router.post("/forgot-password", response_model=s.ForgotOut)
def forgot_password(payload: s.ForgotIn, db: Session = Depends(get_db)):
    return auth_service.forgot_password(db, payload.email)


@router.post("/reset-password", response_model=s.OkOut)
def reset_password(payload: s.ResetIn, db: Session = Depends(get_db)):
    auth_service.reset_password(db, payload)
    return s.OkOut()


# ---------- two-factor setup (user is logged in). There is no endpoint to turn 2FA off. ----------
@router.post("/2fa/setup", response_model=s.TotpSetupOut)
def setup_2fa(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return auth_service.setup_2fa(db, user)


@router.post("/2fa/confirm", response_model=s.OkOut)
def confirm_2fa(payload: s.CodeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    auth_service.confirm_2fa(db, user, payload.code)
    return s.OkOut()
