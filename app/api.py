import json
import os
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import case, func

from app.client_registry import get_client, list_clients
from app.database import get_session_factory
from app.models import ApiCheck, WorkflowOutcome, WorkflowRun, WorkflowStep, init_db

app = FastAPI(title="Agency Monitoring Portal API")


def require_api_key(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
):
    """Guard read/ops endpoints with the agency admin API key.

    Fails closed: if ``PORTAL_API_KEY`` is not configured the endpoint refuses
    to serve rather than running open. Accepts either an ``Authorization:
    Bearer`` header or an ``X-API-Key`` header.
    """
    expected = os.getenv("PORTAL_API_KEY")
    if not expected:
        raise HTTPException(status_code=503, detail="PORTAL_API_KEY not configured")

    presented = x_api_key
    if not presented and authorization and authorization.lower().startswith("bearer "):
        presented = authorization[len("bearer "):].strip()

    if not presented or not secrets.compare_digest(presented, expected):
        raise HTTPException(status_code=401, detail="invalid or missing API key")


def require_ingest_token(x_ingest_token: str | None = Header(default=None)):
    """Guard the workflow ingest endpoint with a dedicated token.

    Fails closed: if ``WORKFLOW_INGEST_TOKEN`` is not configured the endpoint
    refuses writes rather than accepting unauthenticated data.
    """
    expected = os.getenv("WORKFLOW_INGEST_TOKEN")
    if not expected:
        raise HTTPException(status_code=503, detail="WORKFLOW_INGEST_TOKEN not configured")
    if not x_ingest_token or not secrets.compare_digest(x_ingest_token, expected):
        raise HTTPException(status_code=401, detail="unauthorized")


class WorkflowStepIn(BaseModel):
    step_name: str
    step_type: str = "llm"
    success: bool
    latency_ms: float | None = None
    error_message: str | None = None


class WorkflowOutcomeIn(BaseModel):
    outcome_type: str
    outcome_value: str | None = None
    metadata: dict | None = None


class WorkflowRunIn(BaseModel):
    run_id: str = Field(min_length=1)
    workflow_name: str = Field(min_length=1)
    started_at: datetime
    ended_at: datetime | None = None
    success: bool
    total_latency_ms: float | None = None
    total_cost_usd: float | None = None
    steps: list[WorkflowStepIn] = Field(default_factory=list)
    outcomes: list[WorkflowOutcomeIn] = Field(default_factory=list)


@app.get("/api/clients", dependencies=[Depends(require_api_key)])
def clients():
    return [{"slug": c.slug, "name": c.name, "pages_subdir": c.pages_subdir} for c in list_clients()]


@app.get("/api/status/{slug}", dependencies=[Depends(require_api_key)])
def client_status(slug: str):
    try:
        client = get_client(slug)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="client not found")

    session_factory, engine = get_session_factory(client.db_env_var)
    init_db(engine)

    db = session_factory()
    try:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        stats = (
            db.query(
                ApiCheck.provider,
                func.count(ApiCheck.id).label("total"),
                func.sum(case((ApiCheck.success == True, 1), else_=0)).label("successful"),
                func.avg(ApiCheck.latency_ms).label("avg_latency"),
            )
            .filter(ApiCheck.timestamp >= cutoff)
            .group_by(ApiCheck.provider)
            .all()
        )
    finally:
        db.close()

    rows = []
    for s in stats:
        uptime = (s.successful / s.total * 100.0) if s.total else 0.0
        rows.append(
            {
                "provider": s.provider,
                "checks": int(s.total or 0),
                "uptime": round(uptime, 1),
                "avg_latency": round(float(s.avg_latency), 0) if s.avg_latency is not None else None,
            }
        )

    return {"client": {"slug": client.slug, "name": client.name}, "status": rows}


@app.post("/api/workflows/{slug}/runs", dependencies=[Depends(require_ingest_token)])
def ingest_workflow_run(
    slug: str,
    payload: WorkflowRunIn,
):
    try:
        client = get_client(slug)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="client not found")

    session_factory, engine = get_session_factory(client.db_env_var)
    init_db(engine)

    db = session_factory()
    try:
        run = (
            db.query(WorkflowRun)
            .filter(
                WorkflowRun.run_id == payload.run_id,
                WorkflowRun.workflow_name == payload.workflow_name,
            )
            .first()
        )

        if run is None:
            run = WorkflowRun(run_id=payload.run_id, workflow_name=payload.workflow_name)
            db.add(run)
            db.flush()

        run.started_at = payload.started_at
        run.ended_at = payload.ended_at
        run.success = payload.success
        run.total_latency_ms = payload.total_latency_ms
        run.total_cost_usd = payload.total_cost_usd

        db.query(WorkflowStep).filter(WorkflowStep.workflow_run_id == run.id).delete()
        db.query(WorkflowOutcome).filter(WorkflowOutcome.workflow_run_id == run.id).delete()

        for step in payload.steps:
            db.add(
                WorkflowStep(
                    workflow_run_id=run.id,
                    step_name=step.step_name,
                    step_type=step.step_type,
                    success=step.success,
                    latency_ms=step.latency_ms,
                    error_message=step.error_message,
                )
            )

        for outcome in payload.outcomes:
            db.add(
                WorkflowOutcome(
                    workflow_run_id=run.id,
                    outcome_type=outcome.outcome_type,
                    outcome_value=outcome.outcome_value,
                    metadata_json=json.dumps(outcome.metadata) if outcome.metadata else None,
                )
            )

        db.commit()
    finally:
        db.close()

    return {
        "ok": True,
        "client": slug,
        "run_id": payload.run_id,
        "stored_steps": len(payload.steps),
        "stored_outcomes": len(payload.outcomes),
    }


@app.get("/api/workflows/{slug}/summary", dependencies=[Depends(require_api_key)])
def workflow_summary(slug: str, hours: int = 24):
    try:
        client = get_client(slug)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="client not found")

    session_factory, engine = get_session_factory(client.db_env_var)
    init_db(engine)

    db = session_factory()
    try:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        rows = (
            db.query(
                WorkflowRun.workflow_name,
                func.count(WorkflowRun.id).label("total_runs"),
                func.sum(case((WorkflowRun.success == True, 1), else_=0)).label("successful_runs"),
                func.avg(WorkflowRun.total_latency_ms).label("avg_latency_ms"),
                func.avg(WorkflowRun.total_cost_usd).label("avg_cost_usd"),
            )
            .filter(WorkflowRun.started_at >= cutoff)
            .group_by(WorkflowRun.workflow_name)
            .order_by(WorkflowRun.workflow_name)
            .all()
        )
    finally:
        db.close()

    summary = []
    for r in rows:
        total = int(r.total_runs or 0)
        successful = int(r.successful_runs or 0)
        completion_rate = (successful / total * 100.0) if total else 0.0
        summary.append(
            {
                "workflow_name": r.workflow_name,
                "total_runs": total,
                "successful_runs": successful,
                "completion_rate": round(completion_rate, 1),
                "avg_latency_ms": round(float(r.avg_latency_ms), 0) if r.avg_latency_ms is not None else None,
                "avg_cost_usd": round(float(r.avg_cost_usd), 4) if r.avg_cost_usd is not None else None,
            }
        )

    return {"client": {"slug": client.slug, "name": client.name}, "hours": hours, "workflows": summary}


@app.get("/", response_class=HTMLResponse)
def home():
    # Intentionally does not enumerate clients: the client list is sensitive and
    # is served only from the authenticated /api/clients endpoint.
    return (
        "<h1>Agency Monitoring Portal</h1>"
        "<p>Operations API. Authenticated endpoints are available under "
        "<code>/api</code>. Provide your API key via the "
        "<code>Authorization: Bearer &lt;key&gt;</code> or <code>X-API-Key</code> header.</p>"
    )
