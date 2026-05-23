"""
Tests for MCP tool handlers.
StorageClient is fully mocked — no DB, no network.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from memory_server.errors import ToolInputValidationError
from memory_server.mcp_tools import (
    handle_notes_save,
    handle_notes_search,
    handle_notes_update,
    handle_tags_search,
)
from memory_server.models import (
    NoteKind,
    NoteList,
    NoteRecord,
    NoteSearchSort,
    TagList,
    TagSearchResult,
    TagSearchSort,
)

NOW = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
NOTE_ID = uuid4()


def _make_note_record(**overrides) -> NoteRecord:
    defaults = dict(
        id=NOTE_ID,
        raw_text="raw",
        normalized_text="normalized",
        note_kind=NoteKind.note,
        source_ref=None,
        created_at=NOW,
        updated_at=NOW,
        tags=[],
    )
    defaults.update(overrides)
    return NoteRecord(**defaults)


def _mock_storage() -> MagicMock:
    storage = MagicMock()
    storage.create_note = AsyncMock()
    storage.search_notes = AsyncMock()
    storage.update_note = AsyncMock()
    storage.search_tags = AsyncMock()
    return storage


# ── handle_notes_save ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_notes_save_success():
    record = _make_note_record(note_kind=NoteKind.task, tags=["x"])
    storage = _mock_storage()
    storage.create_note.return_value = record

    result = await handle_notes_save(
        {
            "raw_text": "raw",
            "normalized_text": "normalized",
            "note_kind": "task",
            "created_at": NOW.isoformat(),
            "tags": ["x"],
        },
        storage,
    )

    storage.create_note.assert_awaited_once()
    assert result["note_kind"] == "task"
    assert result["tags"] == ["x"]
    assert "id" in result


@pytest.mark.asyncio
async def test_handle_notes_save_invalid_payload():
    storage = _mock_storage()
    with pytest.raises(ToolInputValidationError):
        await handle_notes_save({"raw_text": ""}, storage)
    storage.create_note.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_notes_save_dispatches_to_create_note():
    record = _make_note_record()
    storage = _mock_storage()
    storage.create_note.return_value = record

    await handle_notes_save(
        {
            "raw_text": "r",
            "normalized_text": "n",
            "note_kind": "note",
            "created_at": NOW.isoformat(),
            "tags": [],
        },
        storage,
    )
    storage.create_note.assert_awaited_once()
    storage.search_notes.assert_not_awaited()
    storage.update_note.assert_not_awaited()
    storage.search_tags.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_notes_save_result_shape():
    record = _make_note_record()
    storage = _mock_storage()
    storage.create_note.return_value = record

    result = await handle_notes_save(
        {
            "raw_text": "r",
            "normalized_text": "n",
            "note_kind": "note",
            "created_at": NOW.isoformat(),
            "tags": [],
        },
        storage,
    )
    for key in ("id", "raw_text", "normalized_text", "note_kind", "created_at", "updated_at", "tags"):
        assert key in result


# ── handle_notes_search ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_notes_search_success():
    record = _make_note_record()
    storage = _mock_storage()
    storage.search_notes.return_value = NoteList(items=[record])

    result = await handle_notes_search(
        {"limit": 10, "offset": 0, "sort": "created_at_desc"},
        storage,
    )

    storage.search_notes.assert_awaited_once()
    assert "items" in result
    assert len(result["items"]) == 1


@pytest.mark.asyncio
async def test_handle_notes_search_invalid_payload():
    storage = _mock_storage()
    with pytest.raises(ToolInputValidationError):
        await handle_notes_search({"limit": -1, "offset": 0, "sort": "created_at_desc"}, storage)
    storage.search_notes.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_notes_search_dispatches_to_search_notes():
    storage = _mock_storage()
    storage.search_notes.return_value = NoteList(items=[])

    await handle_notes_search({"limit": 5, "offset": 0, "sort": "created_at_asc"}, storage)
    storage.search_notes.assert_awaited_once()
    storage.create_note.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_notes_search_result_shape():
    storage = _mock_storage()
    storage.search_notes.return_value = NoteList(items=[])

    result = await handle_notes_search({"limit": 5, "offset": 0, "sort": "created_at_asc"}, storage)
    assert "items" in result
    assert isinstance(result["items"], list)


# ── handle_notes_update ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_notes_update_success():
    record = _make_note_record(note_kind=NoteKind.reading)
    storage = _mock_storage()
    storage.update_note.return_value = record

    result = await handle_notes_update(
        {
            "note_id": str(NOTE_ID),
            "operations": [{"kind": "set_note_kind", "note_kind": "reading"}],
        },
        storage,
    )

    storage.update_note.assert_awaited_once()
    assert result["note_kind"] == "reading"


@pytest.mark.asyncio
async def test_handle_notes_update_invalid_payload():
    storage = _mock_storage()
    with pytest.raises(ToolInputValidationError):
        await handle_notes_update({"note_id": "not-a-uuid", "operations": []}, storage)
    storage.update_note.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_notes_update_dispatches_to_update_note():
    record = _make_note_record()
    storage = _mock_storage()
    storage.update_note.return_value = record

    await handle_notes_update(
        {
            "note_id": str(NOTE_ID),
            "operations": [{"kind": "set_note_kind", "note_kind": "note"}],
        },
        storage,
    )
    storage.update_note.assert_awaited_once()
    storage.create_note.assert_not_awaited()
    storage.search_notes.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_notes_update_result_shape():
    record = _make_note_record()
    storage = _mock_storage()
    storage.update_note.return_value = record

    result = await handle_notes_update(
        {
            "note_id": str(NOTE_ID),
            "operations": [{"kind": "set_note_kind", "note_kind": "note"}],
        },
        storage,
    )
    for key in ("id", "raw_text", "normalized_text", "note_kind", "created_at", "updated_at", "tags"):
        assert key in result


# ── handle_tags_search ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_tags_search_success():
    storage = _mock_storage()
    storage.search_tags.return_value = TagList(
        items=[TagSearchResult(name="python", usage_count=3)]
    )

    result = await handle_tags_search(
        {"limit": 10, "offset": 0, "sort": "usage_count_desc"},
        storage,
    )

    storage.search_tags.assert_awaited_once()
    assert len(result["items"]) == 1
    assert result["items"][0]["name"] == "python"


@pytest.mark.asyncio
async def test_handle_tags_search_invalid_payload():
    storage = _mock_storage()
    with pytest.raises(ToolInputValidationError):
        await handle_tags_search({"limit": 0, "offset": 0, "sort": "usage_count_desc"}, storage)
    storage.search_tags.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_tags_search_dispatches_to_search_tags():
    storage = _mock_storage()
    storage.search_tags.return_value = TagList(items=[])

    await handle_tags_search({"limit": 5, "offset": 0, "sort": "name_asc"}, storage)
    storage.search_tags.assert_awaited_once()
    storage.create_note.assert_not_awaited()
    storage.search_notes.assert_not_awaited()
    storage.update_note.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_tags_search_result_shape():
    storage = _mock_storage()
    storage.search_tags.return_value = TagList(items=[])

    result = await handle_tags_search({"limit": 5, "offset": 0, "sort": "name_asc"}, storage)
    assert "items" in result
    assert isinstance(result["items"], list)
