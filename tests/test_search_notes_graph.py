from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.errors import IntentParseError
from backend.memory_client import MemoryClient
from backend.search_notes_graph import build_search_notes_graph


def _memory_client() -> MemoryClient:
    client = MemoryClient("http://127.0.0.1:8001/mcp")
    client.notes_search = AsyncMock(
        return_value={
            "items": [
                {
                    "id": "1",
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
    return client


@pytest.mark.asyncio
async def test_search_graph_builds_final_response():
    graph = build_search_notes_graph(_memory_client())
    state = await graph.ainvoke(
        {
            "search_input": {
                "query": "hello",
                "time_range": None,
                "tags": None,
                "tag_match_mode": None,
                "note_kinds": None,
                "source_refs": None,
                "limit": 10,
                "offset": 0,
                "sort": "created_at_desc",
            }
        }
    )

    assert state["final_response"]["intent"] == "search_notes"
    assert state["final_response"]["message"] == "Found 1 notes."
    assert len(state["final_response"]["result"]["notes"]) == 1


@pytest.mark.asyncio
async def test_search_graph_calls_notes_search_once():
    memory_client = _memory_client()
    graph = build_search_notes_graph(memory_client)

    await graph.ainvoke(
        {
            "search_input": {
                "query": "hello",
                "time_range": None,
                "tags": None,
                "tag_match_mode": None,
                "note_kinds": None,
                "source_refs": None,
                "limit": 10,
                "offset": 0,
                "sort": "created_at_desc",
            }
        }
    )

    memory_client.notes_search.assert_awaited_once()


@pytest.mark.asyncio
async def test_search_graph_preserves_typed_search_input():
    graph = build_search_notes_graph(_memory_client())
    state = await graph.ainvoke(
        {
            "search_input": {
                "query": "hello",
                "time_range": None,
                "tags": ["mcp"],
                "tag_match_mode": "any",
                "note_kinds": ["note"],
                "source_refs": None,
                "limit": 10,
                "offset": 0,
                "sort": "created_at_desc",
            }
        }
    )

    assert state["search_input"]["query"] == "hello"
    assert state["search_input"]["tags"] == ["mcp"]
    assert state["search_input"]["tag_match_mode"] == "any"


@pytest.mark.asyncio
async def test_search_graph_rejects_invalid_typed_search_input():
    graph = build_search_notes_graph(_memory_client())

    with pytest.raises(IntentParseError):
        await graph.ainvoke(
            {
                "search_input": {
                    "query": "hello",
                    "time_range": None,
                    "tags": None,
                    "tag_match_mode": None,
                    "note_kinds": None,
                    "source_refs": None,
                    "limit": 0,
                    "offset": 0,
                    "sort": "created_at_desc",
                }
            }
        )
