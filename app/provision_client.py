import argparse
import json
from pathlib import Path

from app.settings import CLIENT_CONFIG_DIR, DOCS_DIR


def provision_client(slug: str, name: str, db_env_var: str, provider: str, model: str):
    CLIENT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    config_path = CLIENT_CONFIG_DIR / f"{slug}.json"
    if config_path.exists():
        raise FileExistsError(f"Client already exists: {slug}")

    data = {
        "slug": slug,
        "name": name,
        "db_env_var": db_env_var,
        "pages_subdir": f"clients/{slug}",
        "max_success_latency_ms": 30000,
        "providers": [
            {
                "provider": provider,
                "model": model,
            }
        ],
    }

    config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    client_docs = DOCS_DIR / "clients" / slug
    (client_docs / "reports").mkdir(parents=True, exist_ok=True)

    print(f"Provisioned client config: {config_path}")
    print(f"Created docs path: {client_docs}")
    print(f"Remember to set env var: {db_env_var}")


def main():
    parser = argparse.ArgumentParser(description="Provision a new client config.")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--db-env-var", required=True)
    parser.add_argument("--provider", default="google")
    parser.add_argument("--model", default="gemini-2.5-flash")
    args = parser.parse_args()

    provision_client(args.slug, args.name, args.db_env_var, args.provider, args.model)


if __name__ == "__main__":
    main()
