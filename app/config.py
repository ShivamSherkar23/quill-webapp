import os
from pathlib import Path

from sqlalchemy import URL


def read_env(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value

    file_path = os.environ.get(f"{name}_FILE")
    if file_path:
        return Path(file_path).read_text(encoding="utf-8").strip()

    return None


def require_env(name: str) -> str:
    value = read_env(name)
    if value:
        return value
    raise RuntimeError(f"{name} or {name}_FILE must be set")


def get_secret_key() -> str:
    return require_env("SECRET_KEY")


def get_database_url() -> str | URL:
    database_url = read_env("DATABASE_URL")
    if database_url:
        return database_url

    required_names = ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")
    missing = [name for name in required_names if not read_env(name)]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            "DATABASE_URL or PostgreSQL connection settings must be set. "
            f"Missing: {joined}"
        )

    return URL.create(
        drivername=os.environ.get("POSTGRES_DRIVER", "postgresql+asyncpg"),
        username=require_env("POSTGRES_USER"),
        password=require_env("POSTGRES_PASSWORD"),
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=require_env("POSTGRES_DB"),
    )
