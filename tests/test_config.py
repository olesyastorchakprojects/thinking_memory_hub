import pytest

from memory_server.config import load_settings
from memory_server.errors import SettingsError


def test_load_settings_success(monkeypatch):
    monkeypatch.setenv("MEMORY_SERVER_HOST", "localhost")
    monkeypatch.setenv("MEMORY_SERVER_PORT", "8080")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")

    settings = load_settings()

    assert settings.memory_server_host == "localhost"
    assert settings.memory_server_port == 8080
    assert settings.database_url == "postgresql://user:pass@localhost/db"


def test_load_settings_missing_host(monkeypatch):
    monkeypatch.delenv("MEMORY_SERVER_HOST", raising=False)
    monkeypatch.setenv("MEMORY_SERVER_PORT", "8080")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")

    with pytest.raises(SettingsError):
        load_settings()


def test_load_settings_missing_port(monkeypatch):
    monkeypatch.setenv("MEMORY_SERVER_HOST", "localhost")
    monkeypatch.delenv("MEMORY_SERVER_PORT", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")

    with pytest.raises(SettingsError):
        load_settings()


def test_load_settings_missing_database_url(monkeypatch):
    monkeypatch.setenv("MEMORY_SERVER_HOST", "localhost")
    monkeypatch.setenv("MEMORY_SERVER_PORT", "8080")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(SettingsError):
        load_settings()


def test_load_settings_invalid_port(monkeypatch):
    monkeypatch.setenv("MEMORY_SERVER_HOST", "localhost")
    monkeypatch.setenv("MEMORY_SERVER_PORT", "not_a_number")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")

    with pytest.raises(SettingsError):
        load_settings()


def test_load_settings_invalid_database_url(monkeypatch):
    monkeypatch.setenv("MEMORY_SERVER_HOST", "localhost")
    monkeypatch.setenv("MEMORY_SERVER_PORT", "8080")
    monkeypatch.setenv("DATABASE_URL", "mysql://user:pass@localhost/db")

    with pytest.raises(SettingsError):
        load_settings()


def test_load_settings_postgres_plus_scheme(monkeypatch):
    monkeypatch.setenv("MEMORY_SERVER_HOST", "localhost")
    monkeypatch.setenv("MEMORY_SERVER_PORT", "5432")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/db")

    settings = load_settings()
    assert settings.database_url.startswith("postgresql+psycopg://")
