from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.errors import BackendProcessingError, IntentParseError
from backend.memory_client import MemoryClient
from backend.update_note_graph import build_update_note_graph


def _memory_client() -> MemoryClient:
    client = MemoryClient("http://127.0.0.1:8001/mcp")
    client.notes_search = AsyncMock(
        return_value={
            "items": [
                {
                    "id": "123e4567-e89b-12d3-a456-426614174999",
                    "raw_text": "hello",
                    "normalized_text": "hello",
                    "note_kind": "note",
                    "source_ref": None,
                    "created_at": "2024-01-01T00:00:00+00:00",
                    "updated_at": "2024-01-01T00:00:00+00:00",
                    "tags": [],
                }
            ]
        }
    )  # type: ignore[method-assign]
    client.notes_update = AsyncMock(
        return_value={
            "id": "123e4567-e89b-12d3-a456-426614174999",
            "raw_text": "hello",
            "normalized_text": "hello",
            "note_kind": "task",
            "source_ref": None,
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:01:00+00:00",
            "tags": [],
        }
    )  # type: ignore[method-assign]
    return client


@pytest.mark.asyncio
async def test_update_note_graph_updates_latest_note():
    memory_client = _memory_client()
    graph = build_update_note_graph(memory_client)

    state = await graph.ainvoke(
        {
            "update_input": {
                "target_mode": "latest_note",
                "operations": [{"kind": "set_note_kind", "note_kind": "task"}],
            }
        }
    )

    assert state["final_response"]["intent"] == "update_note"
    memory_client.notes_search.assert_awaited_once()
    memory_client.notes_update.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_note_graph_rejects_invalid_update_input():
    graph = build_update_note_graph(_memory_client())

    with pytest.raises(IntentParseError):
        await graph.ainvoke(
            {
                "update_input": {
                    "target_mode": "not-a-real-target",
                    "operations": [{"kind": "set_note_kind", "note_kind": "task"}],
                }
            }
        )


@pytest.mark.asyncio
async def test_update_note_graph_rejects_unresolved_target():
    graph = build_update_note_graph(_memory_client())

    with pytest.raises(BackendProcessingError):
        await graph.ainvoke(
            {
                "update_input": {
                    "target_mode": "unresolved",
                    "operations": [{"kind": "set_note_kind", "note_kind": "task"}],
                }
            }
        )
