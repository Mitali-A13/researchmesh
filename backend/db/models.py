from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from backend.db.database import Base
from datetime import datetime
from backend.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)

    email = Column(String, unique=True, index=True)

    hashed_password = Column(String, nullable=False)


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    topic = Column(String, nullable=False)

    report = Column(Text, nullable=False)

    feedback = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # one row per critique round; deleted automatically with the report
    iterations = relationship(
        "ReportIteration",
        cascade="all, delete-orphan",
        order_by="ReportIteration.round",
    )


class ReportIteration(Base):
    """The critic's score for each round (round 1 = first draft)."""

    __tablename__ = "report_iterations"

    id = Column(Integer, primary_key=True, index=True)

    history_id = Column(
        Integer, ForeignKey("chat_history.id"), nullable=False, index=True
    )

    round = Column(Integer, nullable=False)

    score = Column(Integer, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
