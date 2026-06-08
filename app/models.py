from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
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


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, index=True)
    workflow_name = Column(String, index=True)

    started_at = Column(DateTime, index=True)
    ended_at = Column(DateTime, nullable=True)

    success = Column(Boolean, index=True)
    total_latency_ms = Column(Float, nullable=True)
    total_cost_usd = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class WorkflowStep(Base):
    __tablename__ = "workflow_steps"

    id = Column(Integer, primary_key=True, index=True)
    workflow_run_id = Column(Integer, ForeignKey("workflow_runs.id"), index=True)

    step_name = Column(String, index=True)
    step_type = Column(String, index=True)
    success = Column(Boolean, index=True)

    latency_ms = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class WorkflowOutcome(Base):
    __tablename__ = "workflow_outcomes"

    id = Column(Integer, primary_key=True, index=True)
    workflow_run_id = Column(Integer, ForeignKey("workflow_runs.id"), index=True)

    outcome_type = Column(String, index=True)
    outcome_value = Column(String, nullable=True)
    metadata_json = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)


def init_db(engine):
    Base.metadata.create_all(bind=engine)
