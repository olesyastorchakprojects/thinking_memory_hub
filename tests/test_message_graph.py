from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.errors import IntentParseError
from backend.message_graph import build_message_graph
from backend.memory_client import MemoryClient


def _memory_client() -> MemoryClient:
    client = MemoryClient("http://127.0.0.1:8001/mcp")
    client.notes_save = AsyncMock(
        return_value={
            "id": "1",
            "raw_text": "hello",
            "normalized_text": "hello",
            "note_kind": "note",
            "source_ref": None,
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00",
            "tags": [],
        }
    )  # type: ignore[method-assign]
    return client


@pytest.mark.asyncio
async def test_graph_builds_save_request_and_final_response():
    graph = build_message_graph(_memory_client())
    state = await graph.ainvoke(
        {
            "save_input": {
                "raw_text": "hello world",
                "normalized_text": "hello world",
                "note_kind": "note",
                "created_at": "2024-01-01T00:00:00+00:00",
                "tags": [],
                "source_ref": None,
            }
        }
    )

    assert state["save_input"]["raw_text"] == "hello world"
    assert state["save_input"]["normalized_text"] == "hello world"
    assert state["final_response"]["intent"] == "save_note"
    assert state["final_response"]["message"] == "Note saved."


@pytest.mark.asyncio
async def test_graph_calls_notes_save_once():
    memory_client = _memory_client()
    graph = build_message_graph(memory_client)

    await graph.ainvoke(
        {
            "save_input": {
                "raw_text": "hello world",
                "normalized_text": "hello world",
                "note_kind": "note",
                "created_at": "2024-01-01T00:00:00+00:00",
                "tags": [],
                "source_ref": None,
            }
        }
    )

    memory_client.notes_save.assert_awaited_once()


@pytest.mark.asyncio
async def test_graph_preserves_typed_save_input():
    graph = build_message_graph(_memory_client())
    state = await graph.ainvoke(
        {
            "save_input": {
                "raw_text": "  hello world  ",
                "normalized_text": "hello world",
                "note_kind": "note",
                "created_at": "2024-01-01T00:00:00+00:00",
                "tags": [],
                "source_ref": None,
            }
        }
    )

    assert state["save_input"]["raw_text"] == "  hello world  "
    assert state["save_input"]["normalized_text"] == "hello world"


@pytest.mark.asyncio
async def test_graph_rejects_invalid_typed_save_input():
    graph = build_message_graph(_memory_client())

    with pytest.raises(IntentParseError):
        await graph.ainvoke(
            {
                "save_input": {
                    "raw_text": "hello world",
                    "normalized_text": "",
                    "note_kind": "note",
                    "created_at": "2024-01-01T00:00:00+00:00",
                    "tags": [],
                    "source_ref": None,
                }
            }
        )
