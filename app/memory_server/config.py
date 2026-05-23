import os

from pydantic import BaseModel

from memory_server.errors import SettingsError

_POSTGRES_SCHEMES = ("postgresql://", "postgresql+psycopg://", "postgres://")


class Settings(BaseModel):
    memory_server_host: str
    memory_server_port: int
    database_url: str


def load_settings() -> Settings:
    try:
        host = _require_env("MEMORY_SERVER_HOST")
        port_raw = _require_env("MEMORY_SERVER_PORT")
        database_url = _require_env("DATABASE_URL")

        try:
            port = int(port_raw)
        except ValueError:
            raise SettingsError(f"MEMORY_SERVER_PORT must be an integer, got: {port_raw!r}")

        if not any(database_url.startswith(s) for s in _POSTGRES_SCHEMES):
            raise SettingsError(
                f"DATABASE_URL must be a PostgreSQL connection string, got: {database_url!r}"
            )

        return Settings(
            memory_server_host=host,
            memory_server_port=port,
            database_url=database_url,
        )
    except SettingsError:
        raise
    except Exception as exc:
        raise SettingsError(str(exc)) from exc


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None:
        raise SettingsError(f"Required environment variable {name!r} is not set")
    return value
