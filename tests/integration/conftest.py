"""
Shared fixtures for integration tests.

Requires TEST_DATABASE_URL to point to a dedicated integration-test PostgreSQL database.
The schema from db/schema.sql is applied once per session before any test runs.
Each test that inserts data cleans up via its own fixture teardown using a direct
psycopg connection — tests must not reach into StorageClient internals for cleanup.
"""
from __future__ import annotations

import os
from pathlib import Path

import psycopg
import psycopg.errors
import pytest
import pytest_asyncio

from memory_server.storage_client import StorageClient

_SCHEMA_PATH = Path(__file__).parents[2] / "db" / "schema.sql"


def get_test_database_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def test_database_url() -> str:
    url = get_test_database_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set — skipping integration tests")
    return url


@pytest.fixture(scope="session", autouse=True)
def apply_schema(test_database_url: str) -> None:
    """
    Apply db/schema.sql to the test database once per session.

    The schema file contains a PL/pgSQL function with $$ delimiters whose body
    includes semicolons — splitting on ; would break it. Instead the whole file
    is executed as a single string. psycopg accepts multiple SQL statements in
    one execute() call when autocommit is on.

    On repeated runs the objects already exist, so we catch DuplicateTable /
    DuplicateObject for the whole block and treat it as a no-op: if the tables
    are there the schema is already applied.
    """
    schema_sql = _SCHEMA_PATH.read_text()
    with psycopg.connect(test_database_url, autocommit=True) as conn:
        try:
            conn.execute(schema_sql)
        except (psycopg.errors.DuplicateTable, psycopg.errors.DuplicateObject):
            pass


@pytest_asyncio.fixture
async def storage_client(test_database_url: str) -> StorageClient:
    client = StorageClient(test_database_url)
    await client.open()
    yield client
    await client.close()


def delete_notes_by_source_ref(database_url: str, *source_refs: str) -> None:
    """
    Remove test records by source_ref using a direct synchronous connection.

    Cleanup must not reach into StorageClient internals — this helper owns its
    own connection so tests stay decoupled from pool implementation details.
    """
    if not source_refs:
        return
    with psycopg.connect(database_url) as conn:
        conn.execute(
            "DELETE FROM notes WHERE source_ref = ANY(%s)",
            (list(source_refs),),
        )
        conn.commit()
