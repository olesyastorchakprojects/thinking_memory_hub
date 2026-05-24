from __future__ import annotations

from datetime import datetime, timezone
import os
import uuid

import pytest

from backend.memory_client import MemoryClient
from backend.update_note_graph import build_update_note_graph

pytestmark = pytest.mark.integration


@pytest.fixture
def memory_server_url() -> str:
    value = os.environ.get("MEMORY_SERVER_URL")
    if not value:
        pytest.skip("MEMORY_SERVER_URL is not set for backend integration tests")
    return value


@pytest.mark.asyncio
async def test_update_note_graph_integration(memory_server_url: str):
    client = MemoryClient(memory_server_url)
    await client.open()
    try:
        unique = uuid.uuid4().hex[:8]
        saved = await client.notes_save(
            {
                "raw_text": f"update graph note {unique}",
                "normalized_text": f"update graph note {unique}",
                "note_kind": "note",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "tags": ["update-graph"],
                "source_ref": f"update-graph-{unique}",
            }
        )

        graph = build_update_note_graph(client)
        state = await graph.ainvoke(
            {
                "update_input": {
                    "target_mode": "latest_note",
                    "operations": [{"kind": "set_note_kind", "note_kind": "task"}],
                }
            }
        )
    finally:
        await client.close()

    assert state["final_response"]["intent"] == "update_note"
    assert state["final_response"]["result"]["note"]["id"] == saved["id"]
    assert state["final_response"]["result"]["note"]["note_kind"] == "task"
