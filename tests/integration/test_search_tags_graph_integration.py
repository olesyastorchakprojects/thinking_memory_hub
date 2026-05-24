from __future__ import annotations

import os
import uuid

import pytest

from backend.memory_client import MemoryClient
from backend.search_tags_graph import build_search_tags_graph

pytestmark = pytest.mark.integration


@pytest.fixture
def memory_server_url() -> str:
    value = os.environ.get("MEMORY_SERVER_URL")
    if not value:
        pytest.skip("MEMORY_SERVER_URL is not set for backend integration tests")
    return value


@pytest.mark.asyncio
async def test_search_tags_graph_integration(memory_server_url: str):
    client = MemoryClient(memory_server_url)
    await client.open()
    try:
        unique = uuid.uuid4().hex[:8]
        await client.notes_save(
            {
                "raw_text": f"search tags graph note {unique}",
                "normalized_text": f"search tags graph note {unique}",
                "note_kind": "note",
                "created_at": "2024-01-01T00:00:00+00:00",
                "tags": [f"search-tags-{unique}", "theme-ai"],
                "source_ref": f"search-tags-graph-{unique}",
            }
        )

        graph = build_search_tags_graph(client)
        state = await graph.ainvoke(
            {
                "search_input": {
                    "query": unique,
                    "time_range": None,
                    "note_kinds": None,
                    "source_refs": None,
                    "limit": 10,
                    "offset": 0,
                    "sort": "usage_count_desc",
                }
            }
        )
    finally:
        await client.close()

    assert state["final_response"]["intent"] == "search_tags"
    assert state["final_response"]["result"]["tags"]
