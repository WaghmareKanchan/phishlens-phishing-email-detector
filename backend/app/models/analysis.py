from sqlalchemy import Boolean, Column, Float, ForeignKey, String
from sqlalchemy.orm import relationship

from ..database import Base
from .types import UTCDateTime, new_id, utcnow


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(String, primary_key=True, default=new_id)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email_id = Column(String, ForeignKey("emails.id", ondelete="SET NULL"), nullable=True, index=True)

    # Snapshot of what was analysed. Without it, analysing an e-mail you did NOT save left the
    # History and Admin tables with blank sender/subject.
    sender = Column(String, default="", nullable=False)
    subject = Column(String, default="", nullable=False)
    content_hash = Column(String, nullable=False, index=True)

    ensemble_score = Column(Float, nullable=False)
    verdict = Column(String, nullable=False)                  # "phish" | "warn" | "safe"
    engine = Column(String, default="heuristic", nullable=False)  # "trained" | "heuristic"
    hidden = Column(Boolean, default=False, nullable=False)   # "Clear history" hides, never deletes stats
    analyzed_at = Column(UTCDateTime, default=utcnow, nullable=False, index=True)

    user = relationship("User", back_populates="analyses")
    email = relationship("Email", back_populates="analyses")
    predictions = relationship("Prediction", back_populates="analysis", cascade="all, delete-orphan")


class Prediction(Base):
    """One row per model per analysis (also the junction table Analysis <-> MLModel)."""
    __tablename__ = "predictions"

    id = Column(String, primary_key=True, default=new_id)
    analysis_id = Column(String, ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    model_id = Column(String, ForeignKey("ml_models.id"), nullable=False, index=True)
    score = Column(Float, nullable=False)
    verdict = Column(String, nullable=False)

    analysis = relationship("Analysis", back_populates="predictions")
    model = relationship("MLModel")
