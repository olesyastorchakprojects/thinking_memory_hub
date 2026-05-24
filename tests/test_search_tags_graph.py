from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.errors import IntentParseError
from backend.memory_client import MemoryClient
from backend.search_tags_graph import build_search_tags_graph


def _memory_client() -> MemoryClient:
    client = MemoryClient("http://127.0.0.1:8001/mcp")
    client.tags_search = AsyncMock(
        return_value={
            "items": [
                {
                    "name": "mcp",
                    "usage_count": 2,
                }
            ]
        }
    )  # type: ignore[method-assign]
    return client


@pytest.mark.asyncio
async def test_search_tags_graph_builds_final_response():
    graph = build_search_tags_graph(_memory_client())
    state = await graph.ainvoke(
        {
            "search_input": {
                "query": "mcp",
                "time_range": None,
                "note_kinds": None,
                "source_refs": None,
                "limit": 10,
                "offset": 0,
                "sort": "usage_count_desc",
            }
        }
    )

    assert state["final_response"]["intent"] == "search_tags"
    assert state["final_response"]["message"] == "Found 1 tags."
    assert len(state["final_response"]["result"]["tags"]) == 1


@pytest.mark.asyncio
async def test_search_tags_graph_calls_tags_search_once():
    memory_client = _memory_client()
    graph = build_search_tags_graph(memory_client)

    await graph.ainvoke(
        {
            "search_input": {
                "query": "mcp",
                "time_range": None,
                "note_kinds": None,
                "source_refs": None,
                "limit": 10,
                "offset": 0,
                "sort": "usage_count_desc",
            }
        }
    )

    memory_client.tags_search.assert_awaited_once()


@pytest.mark.asyncio
async def test_search_tags_graph_rejects_invalid_typed_search_input():
    graph = build_search_tags_graph(_memory_client())

    with pytest.raises(IntentParseError):
        await graph.ainvoke(
            {
                "search_input": {
                    "query": "mcp",
                    "time_range": None,
                    "note_kinds": None,
                    "source_refs": None,
                    "limit": 0,
                    "offset": 0,
                    "sort": "usage_count_desc",
                }
            }
        )
