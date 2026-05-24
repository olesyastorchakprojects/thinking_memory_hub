from __future__ import annotations

import os
import uuid

import pytest

from backend.memory_client import MemoryClient
from backend.search_notes_graph import build_search_notes_graph

pytestmark = pytest.mark.integration


@pytest.fixture
def memory_server_url() -> str:
    value = os.environ.get("MEMORY_SERVER_URL")
    if not value:
        pytest.skip("MEMORY_SERVER_URL is not set for backend integration tests")
    return value


@pytest.mark.asyncio
async def test_search_notes_graph_integration(memory_server_url: str):
    client = MemoryClient(memory_server_url)
    await client.open()
    try:
        unique = uuid.uuid4().hex[:8]
        await client.notes_save(
            {
                "raw_text": f"search graph note {unique}",
                "normalized_text": f"search graph note {unique}",
                "note_kind": "note",
                "created_at": "2024-01-01T00:00:00+00:00",
                "tags": ["search-graph"],
                "source_ref": f"search-graph-{unique}",
            }
        )

        graph = build_search_notes_graph(client)
        state = await graph.ainvoke(
            {
                "search_input": {
                    "query": unique,
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
    finally:
        await client.close()

    assert state["final_response"]["intent"] == "search_notes"
    assert state["final_response"]["result"]["notes"]
