"""FastAPI dependencies shared by every controller (authentication / authorization)."""
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from .exceptions import AppError
from .security import decode_token

bearer_scheme = HTTPBearer(auto_error=False)


def client_ip(request: Request) -> str:
    # Behind a reverse proxy start uvicorn with --proxy-headers so this is the real client.
    return request.client.host if request.client else "unknown"


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise AppError(401, "Not authenticated.", code="session_expired")
    claims = decode_token(creds.credentials, expected_scope="access")
    if not claims:
        raise AppError(401, "Your session has expired. Log in again.", code="session_expired")
    user = db.get(User, claims["sub"])
    # token_version changes whenever the password changes, which signs out every other device.
    if not user or user.token_version != claims.get("tv"):
        raise AppError(401, "Your session has expired. Log in again.", code="session_expired")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise AppError(403, "Admin access required.", code="forbidden")
    return user
