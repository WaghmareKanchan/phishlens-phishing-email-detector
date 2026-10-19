from datetime import datetime

from pydantic import BaseModel

from .email import Verdict


class AdminStatsOut(BaseModel):
    total_users: int
    total_emails: int
    total_analyses: int
    users_with_2fa: int
    verdict_counts: dict[str, int]


class AdminUserOut(BaseModel):
    id: str
    name: str
    email: str
    created_at: datetime
    two_factor_enabled: bool
    is_admin: bool
    saved_email_count: int


class AdminActivityOut(BaseModel):
    analyzed_at: datetime
    user: str
    sender: str
    subject: str
    verdict: Verdict
    ensemble_score: float
    engine: str


class ReloadOut(BaseModel):
    loaded: list[str]
    errors: dict[str, str]
