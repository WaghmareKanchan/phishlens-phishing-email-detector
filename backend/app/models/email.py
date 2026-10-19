from sqlalchemy import Column, Float, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from ..database import Base
from .types import UTCDateTime, new_id, utcnow


class Email(Base):
    """An e-mail the user chose to save (also usable as labelled training data)."""
    __tablename__ = "emails"

    id = Column(String, primary_key=True, default=new_id)
    owner_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sender = Column(String, default="", nullable=False)
    subject = Column(String, default="", nullable=False)
    body = Column(Text, default="", nullable=False)
    label = Column(String, default="", nullable=False)       # "phishing" | "legitimate" | ""

    # Result of the most recent analysis OF THIS EXACT TEXT (reset to NULL when the text is edited)
    last_verdict = Column(String, nullable=True)             # "phish" | "warn" | "safe"
    last_score = Column(Float, nullable=True)
    last_analyzed_at = Column(UTCDateTime, nullable=True)

    created_at = Column(UTCDateTime, default=utcnow, nullable=False)
    updated_at = Column(UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False)

    owner = relationship("User", back_populates="emails")
    analyses = relationship("Analysis", back_populates="email")
