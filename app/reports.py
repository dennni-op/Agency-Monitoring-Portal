from datetime import datetime, timedelta
from html import escape
from pathlib import Path

from sqlalchemy import Integer, func

from app.client_registry import get_client
from app.database import get_session_factory
from app.models import ApiCheck, init_db
from app.settings import DOCS_DIR, REPORTS_DIR_NAME


def _query_stats(db, start, end):
    rows = (
        db.query(
            ApiCheck.provider,
            func.count(ApiCheck.id).label("total"),
            func.sum(func.cast(ApiCheck.success, Integer)).label("successful"),
            func.avg(ApiCheck.latency_ms).label("avg_latency"),
        )
        .filter(ApiCheck.timestamp >= start, ApiCheck.timestamp < end)
        .group_by(ApiCheck.provider)
        .order_by(ApiCheck.provider)
        .all()
    )

    data = {}
    for r in rows:
        total = int(r.total or 0)
        successful = int(r.successful or 0)
        data[r.provider] = {
            "total": total,
            "successful": successful,
            "uptime": (successful / total * 100.0) if total else 0.0,
            "avg_latency": float(r.avg_latency) if r.avg_latency is not None else None,
        }
    return data


def _fmt_ms(value):
    if value is None:
        return "N/A"
    return f"{value:.0f}ms"


def _fmt_pct(value):
    return f"{value:.1f}%"


def generate_weekly_report(client_slug: str):
    client = get_client(client_slug)
    session_factory, engine = get_session_factory(client.db_env_var)
    init_db(engine)

    db = session_factory()
    try:
        end = datetime.utcnow()
        start = end - timedelta(days=7)
        data = _query_stats(db, start, end)
    finally:
        db.close()

    reports_dir = DOCS_DIR / client.pages_subdir / REPORTS_DIR_NAME
    reports_dir.mkdir(parents=True, exist_ok=True)

    date_str = end.strftime("%Y-%m-%d")
    filename = f"weekly-report-{date_str}.html"
    out_file = reports_dir / filename

    rows = []
    for provider in sorted(data.keys()):
        s = data[provider]
        rows.append(
            f"<tr><td>{escape(provider)}</td><td>{s['total']}</td><td>{s['successful']}</td><td>{_fmt_pct(s['uptime'])}</td><td>{_fmt_ms(s['avg_latency'])}</td></tr>"
        )

    html = f"""<!doctype html>
<html lang=\"en\"> 
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>{escape(client.name)} Weekly Reliability Report</title>
  <style>
    body {{ font-family: -apple-system, Segoe UI, sans-serif; margin: 2rem auto; max-width: 960px; padding: 0 1rem; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border: 1px solid #ddd; padding: 0.5rem; text-align: left; }}
    th {{ background: #f4f4f4; }}
  </style>
</head>
<body>
  <h1>{escape(client.name)} - Weekly Reliability Report</h1>
  <p>Window: {start.strftime('%Y-%m-%d %H:%M:%S')} to {end.strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
  <table>
    <thead><tr><th>Provider</th><th>Checks</th><th>Success</th><th>Uptime</th><th>Avg Latency</th></tr></thead>
    <tbody>{''.join(rows) if rows else '<tr><td colspan="5">No data.</td></tr>'}</tbody>
  </table>
</body>
</html>
"""
    out_file.write_text(html, encoding="utf-8")

    latest = reports_dir / "latest.html"
    latest.write_text(
        f"<meta http-equiv=\"refresh\" content=\"0; url=./{filename}\">",
        encoding="utf-8",
    )

    index = DOCS_DIR / client.pages_subdir / "index.html"
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(
        f"<h1>{escape(client.name)} Reports</h1><p><a href=\"reports/latest.html\">Open latest report</a></p>",
        encoding="utf-8",
    )

    return out_file


if __name__ == "__main__":
    import os

    slug = os.getenv("CLIENT_SLUG", "acme")
    report_file = generate_weekly_report(slug)
    print(f"Generated: {report_file}")
