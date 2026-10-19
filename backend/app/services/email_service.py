"""Business rules for saved e-mails."""
from __future__ import annotations

import hashlib
from typing import Optional

from sqlalchemy.orm import Session

from ..core.exceptions import AppError
from ..models import Analysis, Email, User
from ..schemas.email import EmailIn


def content_hash(sender: str, subject: str, body: str) -> str:
    """Fingerprint of the text. Lets us attach an analysis verdict to a saved e-mail only if it was
    computed for exactly this text (and lets the client prove it without sending the verdict)."""
    return hashlib.sha256("\x1f".join((sender or "", subject or "", body or "")).encode("utf-8")).hexdigest()


def attach_analysis(email: Email, analysis: Optional[Analysis], user_id: str) -> None:
    """Link `analysis` to `email` iff it belongs to this user and was computed for this exact text."""
    if analysis is None or analysis.user_id != user_id:
        return
    if analysis.content_hash != content_hash(email.sender, email.subject, email.body):
        return
    analysis.email_id = email.id
    email.last_verdict = analysis.verdict
    email.last_score = analysis.ensemble_score
    email.last_analyzed_at = analysis.analyzed_at


def get_owned(db: Session, user: User, email_id: str) -> Email:
    email = db.get(Email, email_id)
    if not email or email.owner_id != user.id:      # 404 (not 403) so ids of others stay invisible
        raise AppError(404, "Email not found.", code="not_found")
    return email


def list_emails(db: Session, user: User) -> list[Email]:
    return (db.query(Email).filter_by(owner_id=user.id)
            .order_by(Email.updated_at.desc()).limit(500).all())


def _new_email(db: Session, user: User, p: EmailIn) -> Email:
    email = Email(owner_id=user.id, sender=p.sender, subject=p.subject, body=p.body, label=p.label)
    db.add(email)
    db.flush()
    if p.analysis_id:
        attach_analysis(email, db.get(Analysis, p.analysis_id), user.id)
    return email


def create_email(db: Session, user: User, p: EmailIn) -> Email:
    email = _new_email(db, user, p)
    db.commit()
    return email


def bulk_create(db: Session, user: User, items: list[EmailIn]) -> int:
    for p in items:
        _new_email(db, user, p)
    db.commit()                      # one commit for the whole batch
    return len(items)


def update_email(db: Session, user: User, email_id: str, p: EmailIn) -> Email:
    email = get_owned(db, user, email_id)
    changed = content_hash(email.sender, email.subject, email.body) != content_hash(p.sender, p.subject, p.body)
    email.sender, email.subject, email.body, email.label = p.sender, p.subject, p.body, p.label
    if changed:   # the old verdict described different text
        email.last_verdict = email.last_score = email.last_analyzed_at = None
    if p.analysis_id:
        attach_analysis(email, db.get(Analysis, p.analysis_id), user.id)
    db.commit()
    return email


def delete_email(db: Session, user: User, email_id: str) -> None:
    email = get_owned(db, user, email_id)
    db.delete(email)                 # analyses keep their snapshot; email_id becomes NULL
    db.commit()
