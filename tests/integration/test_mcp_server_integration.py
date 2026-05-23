"""
Integration tests for the FastMCP server against a real PostgreSQL database.

Tools are invoked in-process through the FastMCP runtime (mcp.call_tool).
No HTTP server is started.

Run with:
    TEST_DATABASE_URL=postgresql://... pytest -m integration
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from memory_server.server import build_server
from memory_server.storage_client import StorageClient
from tests.integration.helpers import delete_notes_by_source_ref

pytestmark = pytest.mark.integration

NOW = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
NOW_ISO = NOW.isoformat()


def _ref(label: str) -> str:
    return f"mcp-integration-{label}-{uuid.uuid4()}"


def _structured(result, *, tool_name: str) -> dict:
    if isinstance(result, tuple):
        assert len(result) == 2, f"{tool_name}: unexpected in-process result shape: {result!r}"
        _, structured = result
        assert structured is not None, f"{tool_name}: structuredContent is missing: {result!r}"
        assert isinstance(structured, dict), (
            f"{tool_name}: structuredContent must be a dict, got "
            f"{type(structured).__name__}: {structured!r}"
        )
        return structured

    assert result.isError is False, f"{tool_name}: unexpected tool error result: {result!r}"
    assert result.structuredContent is not None, (
        f"{tool_name}: structuredContent is missing: {result!r}"
    )
    assert isinstance(result.structuredContent, dict), (
        f"{tool_name}: structuredContent must be a dict, got "
        f"{type(result.structuredContent).__name__}: {result.structuredContent!r}"
    )
    return result.structuredContent


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def mcp_server(storage_client: StorageClient):
    return build_server(storage_client)


# ── build_server ──────────────────────────────────────────────────────────────


async def test_build_server_creates_fastmcp_instance(storage_client: StorageClient) -> None:
    from mcp.server.fastmcp import FastMCP
    mcp = build_server(storage_client)
    assert isinstance(mcp, FastMCP)


async def test_build_server_registers_four_tools(storage_client: StorageClient) -> None:
    mcp = build_server(storage_client)
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert names == {"notes.save", "notes.search", "notes.update", "tags.search"}
    assert all(t.inputSchema is not None for t in tools)
    assert all(t.outputSchema is not None for t in tools)


# ── notes.save ────────────────────────────────────────────────────────────────


async def test_notes_save_persists_note(
    mcp_server, storage_client: StorageClient, test_database_url: str
) -> None:
    ref = _ref("save-basic")
    try:
        result = await mcp_server.call_tool("notes.save", {
            "raw_text": "raw content",
            "normalized_text": "normalized content",
            "note_kind": "note",
            "created_at": NOW_ISO,
            "tags": ["integration"],
            "source_ref": ref,
        })
        data = _structured(result, tool_name="notes.save")
        assert data["source_ref"] == ref
        assert data["note_kind"] == "note"
        assert "integration" in data["tags"]
        assert "id" in data
    finally:
        delete_notes_by_source_ref(test_database_url, ref)


async def test_notes_save_valid_payload_matches_spec(
    mcp_server, storage_client: StorageClient, test_database_url: str
) -> None:
    """Payload satisfying mcp_tool_definitions.md inputSchema must succeed."""
    ref = _ref("save-spec")
    try:
        result = await mcp_server.call_tool("notes.save", {
            "raw_text": "spec raw",
            "normalized_text": "spec normalized",
            "note_kind": "task",
            "created_at": NOW_ISO,
            "tags": ["spec-tag"],
            "source_ref": ref,
        })
        data = _structured(result, tool_name="notes.save")
        assert data["note_kind"] == "task"
        assert data["raw_text"] == "spec raw"
    finally:
        delete_notes_by_source_ref(test_database_url, ref)


# ── notes.search ──────────────────────────────────────────────────────────────


async def test_notes_search_returns_persisted_note(
    mcp_server, storage_client: StorageClient, test_database_url: str
) -> None:
    ref = _ref("search-basic")
    try:
        await mcp_server.call_tool("notes.save", {
            "raw_text": "raw",
            "normalized_text": "normalized",
            "note_kind": "note",
            "created_at": NOW_ISO,
            "tags": [],
            "source_ref": ref,
        })
        result = await mcp_server.call_tool("notes.search", {
            "limit": 10,
            "offset": 0,
            "sort": "created_at_desc",
            "source_refs": [ref],
        })
        data = _structured(result, tool_name="notes.search")
        assert len(data["items"]) == 1
        assert data["items"][0]["source_ref"] == ref
    finally:
        delete_notes_by_source_ref(test_database_url, ref)


async def test_notes_search_result_shape_matches_spec(
    mcp_server, storage_client: StorageClient, test_database_url: str
) -> None:
    """Result shape matches NoteList output contract from mcp_tool_definitions.md."""
    ref = _ref("search-shape")
    try:
        await mcp_server.call_tool("notes.save", {
            "raw_text": "r",
            "normalized_text": "n",
            "note_kind": "reading",
            "created_at": NOW_ISO,
            "tags": ["t"],
            "source_ref": ref,
        })
        result = await mcp_server.call_tool("notes.search", {
            "limit": 1,
            "offset": 0,
            "sort": "created_at_desc",
            "source_refs": [ref],
        })
        data = _structured(result, tool_name="notes.search")
        item = data["items"][0]
        for key in ("id", "raw_text", "normalized_text", "note_kind",
                    "created_at", "updated_at", "tags"):
            assert key in item, f"missing key {key!r} in notes.search item"
    finally:
        delete_notes_by_source_ref(test_database_url, ref)


# ── notes.update ──────────────────────────────────────────────────────────────


async def test_notes_update_applies_through_mcp_boundary(
    mcp_server, storage_client: StorageClient, test_database_url: str
) -> None:
    ref = _ref("update-basic")
    try:
        saved = _structured(
            await mcp_server.call_tool("notes.save", {
                "raw_text": "original",
                "normalized_text": "original normalized",
                "note_kind": "note",
                "created_at": NOW_ISO,
                "tags": ["old"],
                "source_ref": ref,
            }),
            tool_name="notes.save",
        )
        note_id = saved["id"]

        result = await mcp_server.call_tool("notes.update", {
            "note_id": note_id,
            "operations": [
                {"kind": "set_note_kind", "note_kind": "task"},
                {"kind": "replace_tags", "tags": ["new"]},
            ],
        })
        data = _structured(result, tool_name="notes.update")
        assert data["id"] == note_id
        assert data["note_kind"] == "task"
        assert data["tags"] == ["new"]
    finally:
        delete_notes_by_source_ref(test_database_url, ref)


# ── tags.search ───────────────────────────────────────────────────────────────


async def test_tags_search_returns_aggregated_results(
    mcp_server, storage_client: StorageClient, test_database_url: str
) -> None:
    ref1 = _ref("tags-1")
    ref2 = _ref("tags-2")
    shared = f"mcp-shared-{uuid.uuid4().hex[:8]}"
    try:
        for ref in (ref1, ref2):
            await mcp_server.call_tool("notes.save", {
                "raw_text": "r",
                "normalized_text": "n",
                "note_kind": "note",
                "created_at": NOW_ISO,
                "tags": [shared],
                "source_ref": ref,
            })
        result = await mcp_server.call_tool("tags.search", {
            "query": shared,
            "limit": 10,
            "offset": 0,
            "sort": "usage_count_desc",
        })
        data = _structured(result, tool_name="tags.search")
        match = next((i for i in data["items"] if i["name"] == shared), None)
        assert match is not None
        assert match["usage_count"] >= 2
    finally:
        delete_notes_by_source_ref(test_database_url, ref1, ref2)


async def test_tags_search_result_shape_matches_spec(
    mcp_server, storage_client: StorageClient, test_database_url: str
) -> None:
    """Result shape matches TagList output contract."""
    ref = _ref("tags-shape")
    tag = f"shape-tag-{uuid.uuid4().hex[:6]}"
    try:
        await mcp_server.call_tool("notes.save", {
            "raw_text": "r",
            "normalized_text": "n",
            "note_kind": "note",
            "created_at": NOW_ISO,
            "tags": [tag],
            "source_ref": ref,
        })
        result = await mcp_server.call_tool("tags.search", {
            "query": tag,
            "limit": 5,
            "offset": 0,
            "sort": "name_asc",
        })
        data = _structured(result, tool_name="tags.search")
        assert "items" in data
        assert isinstance(data["items"], list)
        if data["items"]:
            assert "name" in data["items"][0]
            assert "usage_count" in data["items"][0]
    finally:
        delete_notes_by_source_ref(test_database_url, ref)
