"""
Integration tests for StorageClient against a real PostgreSQL database.

Run with:
    TEST_DATABASE_URL=postgresql://... pytest -m integration
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from memory_server.errors import StorageConflictError, StorageNotFoundError
from memory_server.models import (
    AddTagsOperation,
    NoteCreateRequest,
    NoteKind,
    NoteSearchRequest,
    NoteSearchSort,
    NoteUpdateRequest,
    RemoveTagsOperation,
    ReplaceTagsOperation,
    SetNoteKindOperation,
    SetNormalizedTextOperation,
    TagSearchRequest,
    TagSearchSort,
)
from memory_server.storage_client import StorageClient
from tests.integration.helpers import delete_notes_by_source_ref

pytestmark = pytest.mark.integration

NOW = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)


def _ref(label: str) -> str:
    """Unique source_ref per test run to isolate data."""
    return f"integration-test-{label}-{uuid.uuid4()}"


def _create_req(
    raw: str = "raw text",
    normalized: str = "normalized text",
    kind: NoteKind = NoteKind.note,
    source_ref: str | None = None,
    tags: list[str] | None = None,
    created_at: datetime = NOW,
) -> NoteCreateRequest:
    return NoteCreateRequest(
        raw_text=raw,
        normalized_text=normalized,
        note_kind=kind,
        source_ref=source_ref,
        created_at=created_at,
        tags=tags or [],
    )


# ── open ──────────────────────────────────────────────────────────────────────


async def test_open_connects_to_real_database(storage_client: StorageClient) -> None:
    assert storage_client._pool is not None


# ── create_note ───────────────────────────────────────────────────────────────


async def test_create_note_returns_record(
    storage_client: StorageClient, test_database_url: str
) -> None:
    ref = _ref("create-basic")
    try:
        req = _create_req(source_ref=ref, tags=["python", "ai"])
        record = await storage_client.create_note(req)
        assert record.id is not None
        assert record.raw_text == req.raw_text
        assert record.normalized_text == req.normalized_text
        assert record.note_kind == NoteKind.note
        assert record.source_ref == ref
        assert set(record.tags) == {"python", "ai"}
    finally:
        delete_notes_by_source_ref(test_database_url, ref)


async def test_create_note_writes_to_notes_tags_note_tags(
    storage_client: StorageClient, test_database_url: str
) -> None:
    ref = _ref("create-rows")
    try:
        await storage_client.create_note(_create_req(source_ref=ref, tags=["x", "y"]))
        result = await storage_client.search_notes(
            NoteSearchRequest(
                limit=1, offset=0, sort=NoteSearchSort.created_at_desc,
                source_refs=[ref],
            )
        )
        assert len(result.items) == 1
        assert set(result.items[0].tags) == {"x", "y"}
    finally:
        delete_notes_by_source_ref(test_database_url, ref)


async def test_create_note_source_ref_uniqueness_raises_conflict(
    storage_client: StorageClient, test_database_url: str
) -> None:
    ref = _ref("create-conflict")
    try:
        await storage_client.create_note(_create_req(source_ref=ref))
        with pytest.raises(StorageConflictError):
            await storage_client.create_note(_create_req(source_ref=ref))
    finally:
        delete_notes_by_source_ref(test_database_url, ref)


# ── search_notes ──────────────────────────────────────────────────────────────


async def test_search_notes_returns_persisted_note(
    storage_client: StorageClient, test_database_url: str
) -> None:
    ref = _ref("search-basic")
    try:
        await storage_client.create_note(_create_req(source_ref=ref, tags=["search-tag"]))
        result = await storage_client.search_notes(
            NoteSearchRequest(
                limit=10, offset=0, sort=NoteSearchSort.created_at_desc,
                source_refs=[ref],
            )
        )
        assert len(result.items) == 1
        assert result.items[0].source_ref == ref
        assert "search-tag" in result.items[0].tags
    finally:
        delete_notes_by_source_ref(test_database_url, ref)


async def test_search_notes_query_filters_by_normalized_text(
    storage_client: StorageClient, test_database_url: str
) -> None:
    ref = _ref("search-query")
    unique_word = f"xyzunique{uuid.uuid4().hex[:8]}"
    try:
        await storage_client.create_note(
            _create_req(normalized=f"contains {unique_word} word", source_ref=ref)
        )
        result = await storage_client.search_notes(
            NoteSearchRequest(
                query=unique_word, limit=10, offset=0, sort=NoteSearchSort.created_at_desc,
            )
        )
        assert any(r.source_ref == ref for r in result.items)
    finally:
        delete_notes_by_source_ref(test_database_url, ref)


# ── update_note ───────────────────────────────────────────────────────────────


async def test_update_note_persists_scalar_changes(
    storage_client: StorageClient, test_database_url: str
) -> None:
    ref = _ref("update-scalar")
    try:
        record = await storage_client.create_note(_create_req(source_ref=ref))
        updated = await storage_client.update_note(
            NoteUpdateRequest(
                note_id=record.id,
                operations=[
                    SetNoteKindOperation(note_kind=NoteKind.task),
                    SetNormalizedTextOperation(normalized_text="updated normalized"),
                ],
            )
        )
        assert updated.note_kind == NoteKind.task
        assert updated.normalized_text == "updated normalized"
        assert updated.id == record.id
    finally:
        delete_notes_by_source_ref(test_database_url, ref)


async def test_update_note_persists_tag_changes_atomically(
    storage_client: StorageClient, test_database_url: str
) -> None:
    ref = _ref("update-tags")
    try:
        record = await storage_client.create_note(_create_req(source_ref=ref, tags=["a", "b"]))

        updated = await storage_client.update_note(
            NoteUpdateRequest(
                note_id=record.id,
                operations=[
                    ReplaceTagsOperation(tags=["c"]),
                    AddTagsOperation(tags=["d"]),
                ],
            )
        )
        assert set(updated.tags) == {"c", "d"}

        updated2 = await storage_client.update_note(
            NoteUpdateRequest(
                note_id=record.id,
                operations=[RemoveTagsOperation(tags=["c"])],
            )
        )
        assert updated2.tags == ["d"]
    finally:
        delete_notes_by_source_ref(test_database_url, ref)


async def test_update_note_missing_raises_not_found(storage_client: StorageClient) -> None:
    with pytest.raises(StorageNotFoundError):
        await storage_client.update_note(
            NoteUpdateRequest(
                note_id=uuid.uuid4(),
                operations=[SetNoteKindOperation(note_kind=NoteKind.note)],
            )
        )


# ── search_tags ───────────────────────────────────────────────────────────────


async def test_search_tags_returns_aggregated_results(
    storage_client: StorageClient, test_database_url: str
) -> None:
    ref1 = _ref("tags-agg-1")
    ref2 = _ref("tags-agg-2")
    shared_tag = f"shared-{uuid.uuid4().hex[:8]}"
    try:
        await storage_client.create_note(_create_req(source_ref=ref1, tags=[shared_tag]))
        await storage_client.create_note(_create_req(source_ref=ref2, tags=[shared_tag]))

        result = await storage_client.search_tags(
            TagSearchRequest(
                query=shared_tag, limit=10, offset=0, sort=TagSearchSort.usage_count_desc,
            )
        )
        match = next((i for i in result.items if i.name == shared_tag), None)
        assert match is not None
        assert match.usage_count >= 2
    finally:
        delete_notes_by_source_ref(test_database_url, ref1, ref2)
