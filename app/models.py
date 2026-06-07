from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class ApiCheck(Base):
    __tablename__ = "api_checks"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    provider = Column(String, index=True)
    model = Column(String)

    latency_ms = Column(Float)
    success = Column(Boolean)
    error_message = Column(Text, nullable=True)


def init_db(engine):
    Base.metadata.create_all(bind=engine)
