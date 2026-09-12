from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.sql import func
from database import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    raw_text = Column(Text, nullable=True)          # full OCR-extracted text
    event_date = Column(String(20), nullable=True)  # "YYYY-MM-DD"
    event_time = Column(String(10), nullable=True)  # "HH:MM"
    priority = Column(String(10), default="medium") # low | medium | high
    category = Column(String(50), default="task")   # task | event | bill | reminder
    source_filename = Column(String(255), nullable=True)
    source_type = Column(String(20), nullable=True)  # image | pdf
    ai_engine = Column(String(20), default="rule-based")  # openai | rule-based
    completed = Column(Boolean, default=False)
    calendar_event_id = Column(String(255), nullable=True)
    calendar_event_link = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
