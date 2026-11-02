from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime
from backend.db.database import Base
from datetime import datetime


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
