from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ModelInfoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    type: str
    trained: bool
    is_real: bool
    accuracy: float
    precision: float
    recall: float
    f1: float
    tn: int
    fp: int
    fn: int
    tp: int
    latency_ms: float
    n_test: int
    dataset: str
    trained_at: Optional[datetime] = None


class ModelsOut(BaseModel):
    engine: str                 # "trained" if at least one model is loaded, else "heuristic"
    notice: Optional[str] = None
    models: list[ModelInfoOut]
