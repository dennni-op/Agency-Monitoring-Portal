# Agency Monitoring Portal (MVP)

This is a practical MVP for an Agency White-Label AI Monitoring Portal.

It lets an agency:
- onboard clients quickly,
- run model reliability checks per client,
- keep tenant data isolated,
- publish branded weekly report pages under client-specific paths.

## Why This Architecture

The MVP is split into simple layers:
- monitor layer: writes checks to each client database,
- report layer: turns data into client-facing weekly HTML,
- registry layer: stores each client config,
- lightweight API layer: gives an internal operational view.

This keeps the first version sellable without building a full SaaS platform.

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy environment file and set values:

```bash
copy .env.example .env
```

Required values for at least one client:
- OPENAI_API_KEY / GOOGLE_API_KEY / ANTHROPIC_API_KEY (as needed)
- DATABASE_URL_<CLIENT>

4. Run monitor for a client:

```bash
python run_monitor.py --client acme
```

5. Generate weekly report for a client:

```bash
python run_weekly_report.py --client acme
```

6. Start API app:

```bash
uvicorn app.api:app --host 0.0.0.0 --port 8000
```

## Client Onboarding Automation

Use the provisioning script to automate setup for a new client:

```bash
python -m app.provision_client --slug acme2 --name "Acme 2" --db-env-var DATABASE_URL_ACME2 --provider google --model gemini-2.5-flash
```

This command does three things:
- creates config file under `configs/clients/`,
- creates docs path under `docs/clients/<slug>/`,
- reminds you which DB environment variable must be set.

## File and Folder Guide

- `requirements.txt`
	- Python dependencies.

- `.env.example`
	- Environment variable template.

- `configs/clients/*.json`
	- Client registry entries (one file per client).
	- Defines slug, DB env var, models, latency threshold, publish path.

- `app/client_registry.py`
	- Loads and validates client config files.
	- Main entry point for fetching client metadata by slug.

- `app/database.py`
	- Resolves DB connection by client-specific env var.
	- Caches SQLAlchemy engine/session per DB URL.

- `app/models.py`
	- Data model (`api_checks`) and schema initialization.

- `app/monitor.py`
	- Executes provider checks for one client.
	- Applies response quality + latency threshold classification.
	- Writes pass/fail records to the client database.

- `app/reports.py`
	- Builds weekly summaries from check data.
	- Publishes client-specific report pages under `docs/clients/<slug>/reports/`.

- `app/provision_client.py`
	- Script-driven client onboarding automation.

- `app/api.py`
	- Minimal operations API to view clients and status.
	- Useful for internal agency operations.

- `run_monitor.py`
	- Convenience entry script for client monitor runs.

- `run_weekly_report.py`
	- Convenience entry script for client weekly report generation.

- `docs/clients/<slug>/`
	- Client-facing published report pages.

## Suggested Production Flow

- Hourly job per client: `python run_monitor.py --client <slug>`
- Weekly job per client: `python run_weekly_report.py --client <slug>`
- Publish `docs/` via GitHub Pages for client-readable links.

## MVP Limits (Intentional)

- No full auth/RBAC yet.
- No billing engine yet.
- No live websocket UI.

These are intentionally deferred so you can validate agency demand first.