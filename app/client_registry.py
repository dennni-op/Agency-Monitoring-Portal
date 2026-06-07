import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

from app.settings import CLIENT_CONFIG_DIR


@dataclass
class ProviderConfig:
    provider: str
    model: str


@dataclass
class ClientConfig:
    slug: str
    name: str
    db_env_var: str
    pages_subdir: str
    max_success_latency_ms: int
    providers: List[ProviderConfig]


def _parse_client_config(path: Path) -> ClientConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))
    providers = [ProviderConfig(**p) for p in raw.get("providers", [])]
    return ClientConfig(
        slug=raw["slug"],
        name=raw["name"],
        db_env_var=raw["db_env_var"],
        pages_subdir=raw.get("pages_subdir", f"clients/{raw['slug']}"),
        max_success_latency_ms=int(raw.get("max_success_latency_ms", 30000)),
        providers=providers,
    )


def list_clients() -> List[ClientConfig]:
    if not CLIENT_CONFIG_DIR.exists():
        return []
    files = sorted(CLIENT_CONFIG_DIR.glob("*.json"))
    return [_parse_client_config(p) for p in files]


def get_client(slug: str) -> ClientConfig:
    path = CLIENT_CONFIG_DIR / f"{slug}.json"
    if not path.exists():
        raise FileNotFoundError(f"Client config not found: {slug}")
    return _parse_client_config(path)
