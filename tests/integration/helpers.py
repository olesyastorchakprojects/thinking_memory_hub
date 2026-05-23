"""Shared helpers for integration tests."""
from __future__ import annotations

import psycopg


def delete_notes_by_source_ref(database_url: str, *source_refs: str) -> None:
    """
    Remove test records by source_ref using a direct synchronous connection.

    Cleanup uses its own connection rather than StorageClient internals so
    tests stay decoupled from pool implementation details.
    """
    if not source_refs:
        return
    with psycopg.connect(database_url) as conn:
        conn.execute(
            "DELETE FROM notes WHERE source_ref = ANY(%s)",
            (list(source_refs),),
        )
        conn.commit()
