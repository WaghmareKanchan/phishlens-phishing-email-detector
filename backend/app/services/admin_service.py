from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import get_settings
from ..ml.registry import ModelRegistry
from ..models import Analysis, Email, User
from ..schemas import admin as s
from . import model_service


def stats(db: Session) -> s.AdminStatsOut:
    counts = {"phish": 0, "warn": 0, "safe": 0}
    for verdict, n in db.query(Analysis.verdict, func.count(Analysis.id)).group_by(Analysis.verdict).all():
        if verdict in counts:
            counts[verdict] = n
    return s.AdminStatsOut(
        total_users=db.query(User).count(), total_emails=db.query(Email).count(),
        total_analyses=db.query(Analysis).count(),
        users_with_2fa=db.query(User).filter_by(two_factor_enabled=True).count(),
        verdict_counts=counts)


def users(db: Session) -> list[s.AdminUserOut]:
    per_owner = dict(db.query(Email.owner_id, func.count(Email.id)).group_by(Email.owner_id).all())
    return [s.AdminUserOut(id=u.id, name=u.name, email=u.email, created_at=u.created_at,
                           two_factor_enabled=u.two_factor_enabled, is_admin=u.is_admin,
                           saved_email_count=per_owner.get(u.id, 0))
            for u in db.query(User).order_by(User.created_at.asc()).all()]


def activity(db: Session, limit: int = 20) -> list[s.AdminActivityOut]:
    rows = (db.query(Analysis, User.name).join(User, User.id == Analysis.user_id)
            .order_by(Analysis.analyzed_at.desc()).limit(limit).all())
    return [s.AdminActivityOut(analyzed_at=a.analyzed_at, user=name, sender=a.sender, subject=a.subject,
                               verdict=a.verdict, ensemble_score=a.ensemble_score, engine=a.engine)
            for a, name in rows]


def reload_models(db: Session, registry: ModelRegistry) -> s.ReloadOut:
    """Pick up freshly trained files without restarting the server."""
    registry.load(get_settings().artifacts_dir)
    model_service.sync_models(db, registry)
    return s.ReloadOut(loaded=registry.loaded_names, errors=dict(registry.errors))
