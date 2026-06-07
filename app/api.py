from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException
from sqlalchemy import case, func

from app.client_registry import get_client, list_clients
from app.database import get_session_factory
from app.models import ApiCheck, init_db

app = FastAPI(title="Agency Monitoring Portal API")


@app.get("/api/clients")
def clients():
    return [{"slug": c.slug, "name": c.name, "pages_subdir": c.pages_subdir} for c in list_clients()]


@app.get("/api/status/{slug}")
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


@app.get("/")
def home():
    items = list_clients()
    links = "".join(
        f"<li><a href='/api/status/{c.slug}'>{c.name}</a> | <a href='/docs/{c.pages_subdir}/index.html'>client report</a></li>"
        for c in items
    )
    return f"<h1>Agency Monitoring Portal</h1><ul>{links or '<li>No clients configured.</li>'}</ul>"
