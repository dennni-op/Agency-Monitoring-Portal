import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_engine_cache = {}
_session_cache = {}


def _normalize_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def get_session_factory(db_env_var: str):
    db_url = os.getenv(db_env_var)
    if not db_url:
        raise RuntimeError(f"Missing required env var: {db_env_var}")

    db_url = _normalize_url(db_url)
    if db_url not in _engine_cache:
        connect_args = {}
        if db_url.startswith("postgresql://"):
            connect_args = {"sslmode": "prefer", "connect_timeout": 10}
        engine = create_engine(db_url, connect_args=connect_args, pool_pre_ping=True)
        _engine_cache[db_url] = engine
        _session_cache[db_url] = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    return _session_cache[db_url], _engine_cache[db_url]
