from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from mcp.types import CallToolResult, TextContent

from backend.errors import MemoryServerError
from backend.memory_client import MemoryClient


def test_extract_payload_prefers_structured_content():
    result = CallToolResult(content=[], structuredContent={"id": "1"})
    assert MemoryClient._extract_payload(result) == {"id": "1"}


def test_extract_payload_parses_text_json():
    result = CallToolResult(
        content=[TextContent(type="text", text=json.dumps({"ok": True}))],
        structuredContent=None,
    )
    assert MemoryClient._extract_payload(result) == {"ok": True}


def test_extract_payload_bad_json_raises():
    result = CallToolResult(
        content=[TextContent(type="text", text="{bad")],
        structuredContent=None,
    )
    with pytest.raises(MemoryServerError):
        MemoryClient._extract_payload(result)


@pytest.mark.asyncio
async def test_notes_save_dispatches_to_call_tool():
    client = MemoryClient("http://127.0.0.1:8001/mcp")
    client._call_tool = AsyncMock(return_value={"id": "1"})  # type: ignore[attr-defined]

    result = await client.notes_save({"raw_text": "x"})

    client._call_tool.assert_awaited_once_with("notes.save", {"raw_text": "x"})  # type: ignore[attr-defined]
    assert result == {"id": "1"}


@pytest.mark.asyncio
async def test_call_tool_requires_open_session():
    client = MemoryClient("http://127.0.0.1:8001/mcp")
    with pytest.raises(MemoryServerError):
        await client.notes_search({})


@pytest.mark.asyncio
async def test_call_tool_remote_failure_maps_to_memory_server_error():
    client = MemoryClient("http://127.0.0.1:8001/mcp")
    session = AsyncMock()
    session.call_tool.side_effect = RuntimeError("boom")
    client._session = session

    with pytest.raises(MemoryServerError):
        await client.tags_search({"query": "x"})

