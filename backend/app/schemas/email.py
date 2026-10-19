from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Label = Literal["", "phishing", "legitimate"]
Verdict = Literal["phish", "warn", "safe"]

MAX_SENDER, MAX_SUBJECT, MAX_BODY = 500, 998, 200_000


class EmailIn(BaseModel):
    sender: str = Field(default="", max_length=MAX_SENDER)
    subject: str = Field(default="", max_length=MAX_SUBJECT)
    body: str = Field(min_length=1, max_length=MAX_BODY)
    label: Label = ""
    # Optional: id returned by /analyze for exactly this text, so the saved e-mail keeps its verdict.
    analysis_id: Optional[str] = None


class EmailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    sender: str
    subject: str
    body: str
    label: str
    last_verdict: Optional[Verdict] = None
    last_score: Optional[float] = None
    last_analyzed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class BulkEmailsIn(BaseModel):
    emails: list[EmailIn] = Field(min_length=1, max_length=500)


class BulkEmailsOut(BaseModel):
    saved: int
