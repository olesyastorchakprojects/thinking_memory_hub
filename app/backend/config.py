from __future__ import annotations

import os

from pydantic import BaseModel

from backend.errors import BackendSettingsError


class BackendSettings(BaseModel):
    backend_host: str
    backend_port: int
    memory_server_url: str
    together_url: str
    together_api_key: str
    together_model: str
    slack_signing_secret: str | None = None
    slack_bot_token: str | None = None
    slack_api_base_url: str = "https://slack.com/api"


def load_settings() -> BackendSettings:
    try:
        host = _require_env("BACKEND_HOST")
        port_raw = _require_env("BACKEND_PORT")
        memory_server_url = _require_env("MEMORY_SERVER_URL")
        together_url = _require_env("TOGETHER_URL")
        together_api_key = _require_env("TOGETHER_API_KEY")
        together_model = _require_env("TOGETHER_MODEL")
        slack_signing_secret = _optional_env("SLACK_SIGNING_SECRET")
        slack_bot_token = _optional_env("SLACK_BOT_TOKEN")
        slack_api_base_url = _optional_env("SLACK_API_BASE_URL") or "https://slack.com/api"

        try:
            port = int(port_raw)
        except ValueError as exc:
            raise BackendSettingsError(
                f"BACKEND_PORT must be an integer, got: {port_raw!r}"
            ) from exc

        if not memory_server_url.startswith(("http://", "https://")):
            raise BackendSettingsError(
                "MEMORY_SERVER_URL must be an HTTP URL, "
                f"got: {memory_server_url!r}"
            )
        if not together_url.startswith(("http://", "https://")):
            raise BackendSettingsError(
                "TOGETHER_URL must be an HTTP URL, "
                f"got: {together_url!r}"
            )
        if not together_api_key.strip():
            raise BackendSettingsError("TOGETHER_API_KEY must be non-empty")
        if not together_model.strip():
            raise BackendSettingsError("TOGETHER_MODEL must be non-empty")
        if bool(slack_signing_secret) != bool(slack_bot_token):
            raise BackendSettingsError(
                "SLACK_SIGNING_SECRET and SLACK_BOT_TOKEN must be set together"
            )
        if slack_signing_secret is not None and not slack_signing_secret.strip():
            raise BackendSettingsError("SLACK_SIGNING_SECRET must be non-empty")
        if slack_bot_token is not None and not slack_bot_token.strip():
            raise BackendSettingsError("SLACK_BOT_TOKEN must be non-empty")
        if not slack_api_base_url.startswith(("http://", "https://")):
            raise BackendSettingsError(
                "SLACK_API_BASE_URL must be an HTTP URL, "
                f"got: {slack_api_base_url!r}"
            )

        return BackendSettings(
            backend_host=host,
            backend_port=port,
            memory_server_url=memory_server_url,
            together_url=together_url,
            together_api_key=together_api_key,
            together_model=together_model,
            slack_signing_secret=slack_signing_secret,
            slack_bot_token=slack_bot_token,
            slack_api_base_url=slack_api_base_url,
        )
    except BackendSettingsError:
        raise
    except Exception as exc:
        raise BackendSettingsError(str(exc)) from exc


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None:
        raise BackendSettingsError(f"Required environment variable {name!r} is not set")
    return value


def _optional_env(name: str) -> str | None:
    return os.environ.get(name)
