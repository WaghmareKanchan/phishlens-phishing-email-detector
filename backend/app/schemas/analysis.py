from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .email import MAX_BODY, MAX_SENDER, MAX_SUBJECT, Label, Verdict


class AnalyzeIn(BaseModel):
    sender: str = Field(default="", max_length=MAX_SENDER)
    subject: str = Field(default="", max_length=MAX_SUBJECT)
    body: str = Field(min_length=1, max_length=MAX_BODY)
    save: bool = False                 # convenience for API users: also store it as a saved e-mail
    label: Label = ""
    # If this text is already a saved e-mail, pass its id: the saved row gets the new verdict.
    email_id: Optional[str] = None


class PredictionOut(BaseModel):
    model_name: str
    model_type: str
    score: float
    verdict: Verdict


class EvidenceOut(BaseModel):
    category: str
    severity: str
    title: str
    detail: str


class SegmentOut(BaseModel):
    text: str
    kind: Optional[str] = None   # url | urg | cred | rew | null


class AnalyzeOut(BaseModel):
    analysis_id: str
    ensemble_score: float
    verdict: Verdict
    engine: str                  # "trained" | "heuristic"
    models_loaded: int
    models_expected: int
    predictions: list[PredictionOut]
    evidence: list[EvidenceOut]
    body_segments: list[SegmentOut]
    email_id: Optional[str] = None


class BatchRowOut(BaseModel):
    row: int
    sender: str
    subject: str
    body: str
    label: str
    verdict: Verdict
    ensemble_score: float
    analysis_id: str


class BatchOut(BaseModel):
    engine: str
    total_rows: int              # rows in the file (capped at the limit)
    skipped_empty: int
    truncated: bool
    results: list[BatchRowOut]


class HistoryItemOut(BaseModel):
    id: str
    sender: str
    subject: str
    verdict: Verdict
    ensemble_score: float
    analyzed_at: datetime
