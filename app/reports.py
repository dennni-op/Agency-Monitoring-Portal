from datetime import datetime, timedelta
from html import escape
from pathlib import Path

from sqlalchemy import Integer, func

from app.analytics import (
    make_operational_recommendation,
    pick_best_provider,
    pick_biggest_regression,
    trend_symbol,
)
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
            func.min(ApiCheck.latency_ms).label("min_latency"),
            func.max(ApiCheck.latency_ms).label("max_latency"),
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
            "min_latency": float(r.min_latency) if r.min_latency is not None else None,
            "max_latency": float(r.max_latency) if r.max_latency is not None else None,
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
        prev_end = start
        prev_start = prev_end - timedelta(days=7)
        current = _query_stats(db, start, end)
        previous = _query_stats(db, prev_start, prev_end)
    finally:
        db.close()

    reports_dir = DOCS_DIR / client.pages_subdir / REPORTS_DIR_NAME
    reports_dir.mkdir(parents=True, exist_ok=True)

    date_str = end.strftime("%Y-%m-%d")
    filename = f"weekly-report-{date_str}.html"
    out_file = reports_dir / filename

    rows = []
    for provider in sorted(current.keys()):
        c = current[provider]
        p = previous.get(provider, {})
        uptime_trend = trend_symbol(c["uptime"], p.get("uptime"), lower_is_better=False)
        latency_trend = trend_symbol(c["avg_latency"], p.get("avg_latency"), lower_is_better=True)
        rows.append(
            "<tr>"
            f"<td>{escape(provider)}</td>"
            f"<td>{c['total']}</td>"
            f"<td>{c['successful']}</td>"
            f"<td>{_fmt_pct(c['uptime'])}</td>"
            f"<td>{_fmt_ms(c['avg_latency'])}</td>"
            f"<td>{_fmt_ms(c['min_latency'])}</td>"
            f"<td>{_fmt_ms(c['max_latency'])}</td>"
            f"<td>{escape(uptime_trend)}</td>"
            f"<td>{escape(latency_trend)}</td>"
            "</tr>"
        )

    total_checks = sum(s["total"] for s in current.values())
    total_success = sum(s["successful"] for s in current.values())
    overall_uptime = (total_success / total_checks * 100.0) if total_checks else 0.0

    best = pick_best_provider(current)
    regression = pick_biggest_regression(current, previous)
    recommendation = make_operational_recommendation(best, regression)

    best_text = best if best else "N/A"
    regression_text = regression["text"] if regression else "No material regression detected"

    html = f"""<!doctype html>
<html lang=\"en\"> 
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>{escape(client.name)} Weekly Reliability Report</title>
  <style>
    body {{ font-family: -apple-system, Segoe UI, sans-serif; margin: 2rem auto; max-width: 960px; padding: 0 1rem; line-height: 1.5; }}
    h1, h2 {{ margin-bottom: 0.4rem; }}
    .meta {{ color: #555; margin-bottom: 1rem; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.75rem; margin: 1rem 0 1.25rem; }}
    .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 0.8rem; }}
    .label {{ font-size: 0.85rem; color: #666; }}
    .value {{ font-size: 1.1rem; font-weight: 600; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
    th, td {{ border: 1px solid #ddd; padding: 0.5rem; text-align: left; }}
    th {{ background: #f4f4f4; }}
    .small {{ color: #666; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <h1>{escape(client.name)} - Weekly Reliability Report</h1>
  <p class="meta">Window: {start.strftime('%Y-%m-%d %H:%M:%S')} to {end.strftime('%Y-%m-%d %H:%M:%S')} UTC</p>

  <div class="cards">
    <div class="card"><div class="label">Total checks</div><div class="value">{total_checks}</div></div>
    <div class="card"><div class="label">Successful checks</div><div class="value">{total_success}</div></div>
    <div class="card"><div class="label">Overall uptime</div><div class="value">{_fmt_pct(overall_uptime)}</div></div>
    <div class="card"><div class="label">Best provider (week)</div><div class="value">{escape(best_text)}</div></div>
  </div>

  <section>
    <h2>Executive Summary</h2>
    <ul>
      <li><strong>Best provider this week:</strong> {escape(best_text)}</li>
      <li><strong>Biggest regression:</strong> {escape(regression_text)}</li>
      <li><strong>Operational recommendation:</strong> {escape(recommendation)}</li>
    </ul>
  </section>

  <section>
    <h2>Provider Breakdown</h2>
    <table>
      <thead>
        <tr>
          <th>Provider</th><th>Checks</th><th>Success</th><th>Uptime</th>
          <th>Avg Latency</th><th>Min</th><th>Max</th>
          <th>Uptime Trend</th><th>Latency Trend</th>
        </tr>
      </thead>
      <tbody>{''.join(rows) if rows else '<tr><td colspan="9">No data.</td></tr>'}</tbody>
    </table>
    <p class="small">Trend compares this week vs the previous 7-day window. Uptime: higher is better. Latency: lower is better.</p>
  </section>
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
