"""
Unit-level contract tests for StorageClient.

Mocks follow the real psycopg async API:
  conn.cursor(row_factory=...) -> async context manager -> AsyncCursor
  cursor.execute(sql, params) -> awaitable
  cursor.fetchone()           -> awaitable -> dict | None
  cursor.fetchall()           -> awaitable -> list[dict]
  conn.transaction()          -> async context manager
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from memory_server.errors import StorageClientError, StorageConflictError, StorageNotFoundError
from memory_server.models import (
    NoteCreateRequest,
    NoteKind,
    NoteSearchRequest,
    NoteSearchSort,
    NoteUpdateRequest,
    SetNoteKindOperation,
    SetNormalizedTextOperation,
    TagSearchRequest,
    TagSearchSort,
)
from memory_server.storage_client import StorageClient

NOW = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
NOTE_ID = uuid4()
DB_URL = "postgresql://test:test@localhost/test"


# ── psycopg async API helpers ────────────────────────────────────────────────


def _make_cursor(fetchone_return=None, fetchall_return=None) -> MagicMock:
    """Return an object that behaves like an async cursor context manager."""
    cursor = AsyncMock()
    cursor.execute = AsyncMock()
    cursor.fetchone = AsyncMock(return_value=fetchone_return)
    cursor.fetchall = AsyncMock(return_value=fetchall_return or [])
    return cursor


def _cursor_cm(cursor: MagicMock) -> MagicMock:
    """Wrap a cursor in an async context manager."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=cursor)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _txn_cm() -> MagicMock:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=None)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _make_conn(cursor_sequence: list[MagicMock] | None = None) -> MagicMock:
    """
    Build a mock AsyncConnection.

    cursor_sequence: list of cursors returned by successive conn.cursor() calls.
    If None, every cursor() call returns a fresh default cursor.
    """
    conn = MagicMock()
    conn.transaction = MagicMock(return_value=_txn_cm())

    if cursor_sequence is not None:
        cms = [_cursor_cm(c) for c in cursor_sequence]
        conn.cursor = MagicMock(side_effect=cms)
    else:
        conn.cursor = MagicMock(side_effect=lambda **kw: _cursor_cm(_make_cursor()))

    return conn


def _pool_with_conn(conn: MagicMock) -> MagicMock:
    pool = MagicMock()
    conn_cm = MagicMock()
    conn_cm.__aenter__ = AsyncMock(return_value=conn)
    conn_cm.__aexit__ = AsyncMock(return_value=False)
    pool.connection = MagicMock(return_value=conn_cm)
    return pool


def _note_row(
    note_id: UUID = NOTE_ID,
    raw_text: str = "raw",
    normalized_text: str = "normalized",
    note_kind: str = "note",
    source_ref: str | None = None,
    created_at: datetime = NOW,
    updated_at: datetime = NOW,
) -> dict:
    return {
        "id": note_id,
        "raw_text": raw_text,
        "normalized_text": normalized_text,
        "note_kind": note_kind,
        "source_ref": source_ref,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _tag_rows(note_id: UUID, names: list[str]) -> list[dict]:
    return [{"note_id": note_id, "name": n} for n in names]


# ── open / close ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_open_initializes_pool():
    client = StorageClient(DB_URL)
    mock_pool = AsyncMock()
    with patch("memory_server.storage_client.AsyncConnectionPool", return_value=mock_pool):
        await client.open()
    mock_pool.open.assert_awaited_once()
    assert client._pool is mock_pool


@pytest.mark.asyncio
async def test_close_closes_pool():
    client = StorageClient(DB_URL)
    mock_pool = AsyncMock()
    client._pool = mock_pool
    await client.close()
    mock_pool.close.assert_awaited_once()
    assert client._pool is None


# ── create_note ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_note_returns_note_record():
    # cursor 0: INSERT RETURNING  cursor 1: tag upsert (execute ×N)  cursor 2: note_tags INSERT
    # cursor 3: _fetch_tags_for_notes SELECT
    note_row = _note_row(note_kind="task")
    insert_cur = _make_cursor(fetchone_return=note_row)
    tag_upsert_cur = _make_cursor()
    fetch_tags_cur = _make_cursor(fetchall_return=_tag_rows(NOTE_ID, ["python", "ai"]))

    conn = _make_conn([insert_cur, tag_upsert_cur, fetch_tags_cur])
    client = StorageClient(DB_URL)
    client._pool = _pool_with_conn(conn)

    request = NoteCreateRequest(
        raw_text="raw",
        normalized_text="normalized",
        note_kind=NoteKind.task,
        created_at=NOW,
        tags=["python", "ai"],
    )
    result = await client.create_note(request)

    assert result.id == NOTE_ID
    assert result.note_kind == NoteKind.task
    assert set(result.tags) == {"python", "ai"}
    insert_cur.execute.assert_awaited()
    insert_cur.fetchone.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_note_conflict_raises_storage_conflict_error():
    import psycopg.errors

    insert_cur = _make_cursor()
    insert_cur.execute = AsyncMock(side_effect=psycopg.errors.UniqueViolation())
    conn = _make_conn([insert_cur])
    client = StorageClient(DB_URL)
    client._pool = _pool_with_conn(conn)

    request = NoteCreateRequest(
        raw_text="raw",
        normalized_text="norm",
        note_kind=NoteKind.note,
        source_ref="dup-ref",
        created_at=NOW,
        tags=[],
    )
    with pytest.raises(StorageConflictError):
        await client.create_note(request)


# ── search_notes ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_notes_returns_note_list():
    search_cur = _make_cursor(fetchall_return=[_note_row()])
    tags_cur = _make_cursor(fetchall_return=_tag_rows(NOTE_ID, ["tag1"]))

    conn = _make_conn([search_cur, tags_cur])
    client = StorageClient(DB_URL)
    client._pool = _pool_with_conn(conn)

    request = NoteSearchRequest(limit=10, offset=0, sort=NoteSearchSort.created_at_desc)
    result = await client.search_notes(request)

    assert len(result.items) == 1
    assert result.items[0].tags == ["tag1"]
    search_cur.execute.assert_awaited_once()
    search_cur.fetchall.assert_awaited_once()


@pytest.mark.asyncio
async def test_search_notes_tags_without_tag_match_mode_raises():
    client = StorageClient(DB_URL)
    client._pool = MagicMock()

    request = NoteSearchRequest(
        tags=["python"],
        tag_match_mode=None,
        limit=10,
        offset=0,
        sort=NoteSearchSort.created_at_desc,
    )
    with pytest.raises(StorageClientError):
        await client.search_notes(request)


# ── update_note ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_note_not_found_raises():
    select_cur = _make_cursor(fetchone_return=None)
    conn = _make_conn([select_cur])
    client = StorageClient(DB_URL)
    client._pool = _pool_with_conn(conn)

    request = NoteUpdateRequest(
        note_id=uuid4(),
        operations=[{"kind": "set_note_kind", "note_kind": "task"}],
    )
    with pytest.raises(StorageNotFoundError):
        await client.update_note(request)


@pytest.mark.asyncio
async def test_update_note_set_note_kind():
    select_cur = _make_cursor(fetchone_return={"id": NOTE_ID})
    update_cur = _make_cursor()
    fetch_note_cur = _make_cursor(fetchone_return=_note_row(note_kind="task"))
    fetch_tags_cur = _make_cursor(fetchall_return=_tag_rows(NOTE_ID, ["x"]))

    conn = _make_conn([select_cur, update_cur, fetch_note_cur, fetch_tags_cur])
    client = StorageClient(DB_URL)
    client._pool = _pool_with_conn(conn)

    request = NoteUpdateRequest(
        note_id=NOTE_ID,
        operations=[SetNoteKindOperation(note_kind=NoteKind.task)],
    )
    result = await client.update_note(request)
    assert result.note_kind == NoteKind.task
    update_cur.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_note_set_normalized_text():
    select_cur = _make_cursor(fetchone_return={"id": NOTE_ID})
    update_cur = _make_cursor()
    fetch_note_cur = _make_cursor(fetchone_return=_note_row(normalized_text="new text"))
    fetch_tags_cur = _make_cursor(fetchall_return=[])

    conn = _make_conn([select_cur, update_cur, fetch_note_cur, fetch_tags_cur])
    client = StorageClient(DB_URL)
    client._pool = _pool_with_conn(conn)

    request = NoteUpdateRequest(
        note_id=NOTE_ID,
        operations=[SetNormalizedTextOperation(normalized_text="new text")],
    )
    result = await client.update_note(request)
    assert result.normalized_text == "new text"


@pytest.mark.asyncio
async def test_update_note_atomicity_multiple_operations():
    """All operations must be applied inside a single transaction."""
    select_cur = _make_cursor(fetchone_return={"id": NOTE_ID})
    update_cur = _make_cursor()
    fetch_note_cur = _make_cursor(fetchone_return=_note_row(note_kind="reading"))
    fetch_tags_cur = _make_cursor(fetchall_return=[])

    conn = _make_conn([select_cur, update_cur, fetch_note_cur, fetch_tags_cur])
    client = StorageClient(DB_URL)
    client._pool = _pool_with_conn(conn)

    request = NoteUpdateRequest(
        note_id=NOTE_ID,
        operations=[
            SetNoteKindOperation(note_kind=NoteKind.reading),
            SetNormalizedTextOperation(normalized_text="updated"),
        ],
    )
    await client.update_note(request)
    # transaction() called exactly once → atomicity
    conn.transaction.assert_called_once()


# ── search_tags ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_tags_returns_tag_list():
    tags_cur = _make_cursor(
        fetchall_return=[
            {"name": "python", "usage_count": 5},
            {"name": "ai", "usage_count": 2},
        ]
    )
    conn = _make_conn([tags_cur])
    client = StorageClient(DB_URL)
    client._pool = _pool_with_conn(conn)

    request = TagSearchRequest(limit=10, offset=0, sort=TagSearchSort.usage_count_desc)
    result = await client.search_tags(request)

    assert len(result.items) == 2
    assert result.items[0].name == "python"
    assert result.items[0].usage_count == 5
    tags_cur.execute.assert_awaited_once()
    tags_cur.fetchall.assert_awaited_once()
