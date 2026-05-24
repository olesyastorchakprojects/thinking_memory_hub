from __future__ import annotations

import os
import uuid

import pytest

from backend.memory_client import MemoryClient

pytestmark = pytest.mark.integration


@pytest.fixture
def memory_server_url() -> str:
    value = os.environ.get("MEMORY_SERVER_URL")
    if not value:
        pytest.skip("MEMORY_SERVER_URL is not set for backend integration tests")
    return value


@pytest.mark.asyncio
async def test_memory_client_can_call_notes_save(memory_server_url: str):
    client = MemoryClient(memory_server_url)
    await client.open()
    try:
        unique = uuid.uuid4().hex[:8]
        result = await client.notes_save(
            {
                "raw_text": f"backend save {unique}",
                "normalized_text": f"backend save {unique}",
                "note_kind": "note",
                "created_at": "2024-01-01T00:00:00+00:00",
                "tags": ["backend-integration"],
                "source_ref": f"backend-memory-{unique}",
            }
        )
    finally:
        await client.close()
    assert result["raw_text"].startswith("backend save")


@pytest.mark.asyncio
async def test_memory_client_can_call_notes_search(memory_server_url: str):
    client = MemoryClient(memory_server_url)
    await client.open()
    try:
        result = await client.notes_search(
            {
                "query": "backend",
                "time_range": None,
                "tags": None,
                "tag_match_mode": None,
                "note_kinds": None,
                "source_refs": None,
                "limit": 5,
                "offset": 0,
                "sort": "created_at_desc",
            }
        )
    finally:
        await client.close()
    assert "items" in result


@pytest.mark.asyncio
async def test_memory_client_can_call_tags_search(memory_server_url: str):
    client = MemoryClient(memory_server_url)
    await client.open()
    try:
        result = await client.tags_search(
            {
                "query": "backend-integration",
                "time_range": None,
                "note_kinds": None,
                "source_refs": None,
                "limit": 5,
                "offset": 0,
                "sort": "usage_count_desc",
            }
        )
    finally:
        await client.close()
    assert "items" in result
