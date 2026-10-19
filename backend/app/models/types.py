import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Stores UTC, always returns timezone-AWARE datetimes.

    Plain SQLAlchemy DateTime on SQLite drops the timezone, so the API used to send
    "2026-10-07T04:44:22" (no "Z"). Browsers read that as LOCAL time, so every timestamp was
    shifted by the user's UTC offset (5h30m in India). With this type the API sends "...Z".
    """
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        return None if value is None else value.replace(tzinfo=timezone.utc)
