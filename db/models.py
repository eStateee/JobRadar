import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from db.database import Base
import enum

class VacancyStatus(str, enum.Enum):
    raw = "raw"
    analyzed = "analyzed"
    rejected = "rejected"
    sent = "sent"
    error = "error"

class User(Base):
    __tablename__ = 'users'
    tg_user_id = Column(Integer, primary_key=True, index=True)

class Profile(Base):
    __tablename__ = 'profile'
    id = Column(Integer, primary_key=True, index=True)
    resume_raw_text = Column(Text, nullable=True)
    resume_summary_json = Column(JSON, nullable=True)
    filters_raw_text = Column(Text, nullable=True)
    filters_summary_json = Column(JSON, nullable=True)
    min_match_score = Column(Integer, default=70)
    schedule_times = Column(JSON, default=["09:00", "18:00"])
    timezone = Column(String, default="Europe/Moscow")

class Channel(Base):
    __tablename__ = 'channels'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    is_active = Column(Boolean, default=True)
    last_collected_message_id = Column(Integer, nullable=True)
    backfill_completed = Column(Boolean, default=False)

    vacancies = relationship("Vacancy", back_populates="channel", cascade="all, delete-orphan")

class Vacancy(Base):
    __tablename__ = 'vacancies'
    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey('channels.id'))
    message_id = Column(Integer)
    post_url = Column(String, unique=True, index=True)
    raw_text = Column(Text)
    posted_at = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(SQLEnum(VacancyStatus), default=VacancyStatus.raw)
    match_score = Column(Integer, nullable=True)
    match_reason = Column(Text, nullable=True)
    extracted_data = Column(JSON, nullable=True)

    channel = relationship("Channel", back_populates="vacancies")
