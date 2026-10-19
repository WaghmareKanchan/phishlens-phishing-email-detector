from sqlalchemy import Boolean, Column, Float, Integer, String

from ..database import Base
from .types import UTCDateTime, new_id


class MLModel(Base):
    """One row per model in the ensemble, holding the metrics measured on the held-out test set.

    The rows are (re)filled from backend/artifacts/metrics.json by model_service.sync_models().
    `trained`  -> the model file exists and was loaded into memory.
    `is_real`  -> trained AND evaluated on a real dataset (not the synthetic demo generator).
    """
    __tablename__ = "ml_models"

    id = Column(String, primary_key=True, default=new_id)
    name = Column(String, nullable=False, unique=True)
    type = Column(String, nullable=False)          # "ML" | "DL" | "RULES"
    trained = Column(Boolean, default=False, nullable=False)
    is_real = Column(Boolean, default=False, nullable=False)

    accuracy = Column(Float, default=0.0, nullable=False)   # all metrics in percent (0..100)
    precision = Column(Float, default=0.0, nullable=False)
    recall = Column(Float, default=0.0, nullable=False)
    f1 = Column(Float, default=0.0, nullable=False)
    tn = Column(Integer, default=0, nullable=False)
    fp = Column(Integer, default=0, nullable=False)
    fn = Column(Integer, default=0, nullable=False)
    tp = Column(Integer, default=0, nullable=False)
    latency_ms = Column(Float, default=0.0, nullable=False)  # per e-mail, measured on the test set
    n_test = Column(Integer, default=0, nullable=False)
    dataset = Column(String, default="", nullable=False)
    trained_at = Column(UTCDateTime, nullable=True)
