import pytest

from backend.config import load_settings
from backend.errors import BackendSettingsError


def test_load_settings_success(monkeypatch):
    monkeypatch.setenv("BACKEND_HOST", "127.0.0.1")
    monkeypatch.setenv("BACKEND_PORT", "8081")
    monkeypatch.setenv("MEMORY_SERVER_URL", "http://127.0.0.1:8001/mcp")
    monkeypatch.setenv("TOGETHER_URL", "https://api.together.xyz")
    monkeypatch.setenv("TOGETHER_API_KEY", "key")
    monkeypatch.setenv("TOGETHER_MODEL", "openai/gpt-oss-20b")
    monkeypatch.delenv("SLACK_SIGNING_SECRET", raising=False)
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_API_BASE_URL", raising=False)

    settings = load_settings()

    assert settings.backend_host == "127.0.0.1"
    assert settings.backend_port == 8081
    assert settings.memory_server_url == "http://127.0.0.1:8001/mcp"
    assert settings.together_url == "https://api.together.xyz"
    assert settings.together_api_key == "key"
    assert settings.together_model == "openai/gpt-oss-20b"
    assert settings.slack_signing_secret is None
    assert settings.slack_bot_token is None
    assert settings.slack_api_base_url == "https://slack.com/api"


def test_load_settings_missing_env(monkeypatch):
    monkeypatch.delenv("BACKEND_HOST", raising=False)
    monkeypatch.delenv("BACKEND_PORT", raising=False)
    monkeypatch.delenv("MEMORY_SERVER_URL", raising=False)
    monkeypatch.delenv("TOGETHER_URL", raising=False)
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    monkeypatch.delenv("TOGETHER_MODEL", raising=False)
    monkeypatch.delenv("SLACK_SIGNING_SECRET", raising=False)
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_API_BASE_URL", raising=False)

    with pytest.raises(BackendSettingsError):
        load_settings()


def test_load_settings_invalid_port(monkeypatch):
    monkeypatch.setenv("BACKEND_HOST", "127.0.0.1")
    monkeypatch.setenv("BACKEND_PORT", "abc")
    monkeypatch.setenv("MEMORY_SERVER_URL", "http://127.0.0.1:8001/mcp")
    monkeypatch.setenv("TOGETHER_URL", "https://api.together.xyz")
    monkeypatch.setenv("TOGETHER_API_KEY", "key")
    monkeypatch.setenv("TOGETHER_MODEL", "openai/gpt-oss-20b")

    with pytest.raises(BackendSettingsError):
        load_settings()


def test_load_settings_invalid_memory_server_url(monkeypatch):
    monkeypatch.setenv("BACKEND_HOST", "127.0.0.1")
    monkeypatch.setenv("BACKEND_PORT", "8081")
    monkeypatch.setenv("MEMORY_SERVER_URL", "postgresql://localhost/db")
    monkeypatch.setenv("TOGETHER_URL", "https://api.together.xyz")
    monkeypatch.setenv("TOGETHER_API_KEY", "key")
    monkeypatch.setenv("TOGETHER_MODEL", "openai/gpt-oss-20b")

    with pytest.raises(BackendSettingsError):
        load_settings()


def test_load_settings_with_slack(monkeypatch):
    monkeypatch.setenv("BACKEND_HOST", "127.0.0.1")
    monkeypatch.setenv("BACKEND_PORT", "8081")
    monkeypatch.setenv("MEMORY_SERVER_URL", "http://127.0.0.1:8001/mcp")
    monkeypatch.setenv("TOGETHER_URL", "https://api.together.xyz")
    monkeypatch.setenv("TOGETHER_API_KEY", "key")
    monkeypatch.setenv("TOGETHER_MODEL", "openai/gpt-oss-20b")
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "secret")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-token")
    monkeypatch.setenv("SLACK_API_BASE_URL", "https://slack.test/api")

    settings = load_settings()

    assert settings.slack_signing_secret == "secret"
    assert settings.slack_bot_token == "xoxb-token"
    assert settings.slack_api_base_url == "https://slack.test/api"


def test_load_settings_rejects_partial_slack_config(monkeypatch):
    monkeypatch.setenv("BACKEND_HOST", "127.0.0.1")
    monkeypatch.setenv("BACKEND_PORT", "8081")
    monkeypatch.setenv("MEMORY_SERVER_URL", "http://127.0.0.1:8001/mcp")
    monkeypatch.setenv("TOGETHER_URL", "https://api.together.xyz")
    monkeypatch.setenv("TOGETHER_API_KEY", "key")
    monkeypatch.setenv("TOGETHER_MODEL", "openai/gpt-oss-20b")
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "secret")
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)

    with pytest.raises(BackendSettingsError):
        load_settings()
