import pytest

from app.config import get_database_url, get_secret_key


def clear_config_env(monkeypatch):
    names = (
        "DATABASE_URL",
        "DATABASE_URL_FILE",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_PASSWORD_FILE",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DRIVER",
        "SECRET_KEY",
        "SECRET_KEY_FILE",
    )
    for name in names:
        monkeypatch.delenv(name, raising=False)


def test_database_url_can_be_built_from_postgres_env(monkeypatch):
    clear_config_env(monkeypatch)
    monkeypatch.setenv("POSTGRES_DB", "custom_db")
    monkeypatch.setenv("POSTGRES_USER", "custom_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "custom password")
    monkeypatch.setenv("POSTGRES_HOST", "postgres.example.com")
    monkeypatch.setenv("POSTGRES_PORT", "6543")

    url = get_database_url()

    assert url.database == "custom_db"
    assert url.username == "custom_user"
    assert url.password == "custom password"
    assert url.host == "postgres.example.com"
    assert url.port == 6543


def test_database_url_requires_runtime_database_settings(monkeypatch):
    clear_config_env(monkeypatch)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        get_database_url()


def test_secret_key_can_be_read_from_file(monkeypatch, tmp_path):
    clear_config_env(monkeypatch)
    secret_file = tmp_path / "secret_key"
    secret_file.write_text("file-secret-key\n", encoding="utf-8")
    monkeypatch.setenv("SECRET_KEY_FILE", str(secret_file))

    assert get_secret_key() == "file-secret-key"
