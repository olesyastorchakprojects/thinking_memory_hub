from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os
import uuid
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from backend.input_extractor import StructuredInputExtractor
from backend.intent_classifier import IntentClassifier
from backend.memory_client import MemoryClient
from backend.message_service import MessageService
from backend.models import BackendIntent, ClassifierConfidence, IntentClassificationResult
from backend.server import build_app
from memory_server.models import (
    NoteCreateRequest,
    NoteSearchRequest,
    NoteSearchSort,
    TagSearchRequest,
    TagSearchSort,
)
from backend.models import UpdateExtractionResult, UpdateTargetMode

pytestmark = pytest.mark.integration


@pytest.fixture
def memory_server_url() -> str:
    value = os.environ.get("MEMORY_SERVER_URL")
    if not value:
        pytest.skip("MEMORY_SERVER_URL is not set for backend integration tests")
    return value


def _classifier_for(intent: BackendIntent) -> IntentClassifier:
    classifier = MagicMock(spec=IntentClassifier)
    classifier.classify = AsyncMock(
        return_value=IntentClassificationResult(
            intent=intent,
            reason=f"Routed to {intent.value}.",
            confidence=ClassifierConfidence.high,
        )
    )
    return classifier


def _extractor_for(
    *,
    save_input: NoteCreateRequest | None = None,
    search_input: NoteSearchRequest | None = None,
    search_tags_input: TagSearchRequest | None = None,
    update_input: UpdateExtractionResult | None = None,
) -> StructuredInputExtractor:
    extractor = MagicMock(spec=StructuredInputExtractor)
    extractor.extract_save_input = AsyncMock(return_value=save_input)
    extractor.extract_search_notes_input = AsyncMock(return_value=search_input)
    extractor.extract_search_tags_input = AsyncMock(return_value=search_tags_input)
    extractor.extract_update_note_input = AsyncMock(return_value=update_input)
    return extractor


@asynccontextmanager
async def _api_client(
    memory_server_url: str,
    *,
    intent: BackendIntent,
    save_input: NoteCreateRequest | None = None,
    search_input: NoteSearchRequest | None = None,
    search_tags_input: TagSearchRequest | None = None,
    update_input: UpdateExtractionResult | None = None,
):
    memory_client = MemoryClient(memory_server_url)
    await memory_client.open()
    try:
        app = build_app(
            MessageService(
                memory_client=memory_client,
                intent_classifier=_classifier_for(intent),
                input_extractor=_extractor_for(
                    save_input=save_input,
                    search_input=search_input,
                    search_tags_input=search_tags_input,
                    update_input=update_input,
                ),
            )
        )
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            yield client
    finally:
        await memory_client.close()


@pytest.mark.asyncio
async def test_backend_health_integration(memory_server_url: str):
    async with _api_client(
        memory_server_url,
        intent=BackendIntent.save_note,
        save_input=NoteCreateRequest(
            raw_text="unused",
            normalized_text="unused",
            note_kind="note",
            source_ref=None,
            created_at="2024-01-01T00:00:00+00:00",
            tags=[],
        ),
    ) as api_client:
        response = await api_client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_backend_save_flow(memory_server_url: str):
    unique = uuid.uuid4().hex[:8]
    async with _api_client(
        memory_server_url,
        intent=BackendIntent.save_note,
        save_input=NoteCreateRequest(
            raw_text=f"backend note {unique}",
            normalized_text=f"backend note {unique}",
            note_kind="note",
            source_ref=f"backend-save-{unique}",
            created_at="2024-01-01T00:00:00+00:00",
            tags=["backend-save"],
        ),
    ) as api_client:
        response = await api_client.post(
            "/api/message", json={"text": f"backend note {unique}"}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "save_note"
    assert data["result"]["note"]["raw_text"] == f"backend note {unique}"
    assert data["result"]["note"]["normalized_text"] == f"backend note {unique}"


@pytest.mark.asyncio
async def test_backend_search_notes_flow(memory_server_url: str):
    unique = uuid.uuid4().hex[:8]
    client = MemoryClient(memory_server_url)
    await client.open()
    try:
        await client.notes_save(
            {
                "raw_text": f"backend search note {unique}",
                "normalized_text": f"backend search note {unique}",
                "note_kind": "note",
                "created_at": "2024-01-01T00:00:00+00:00",
                "tags": ["backend-search"],
                "source_ref": f"backend-search-{unique}",
            }
        )
    finally:
        await client.close()

    async with _api_client(
        memory_server_url,
        intent=BackendIntent.search_notes,
        search_input=NoteSearchRequest(
            query=unique,
            time_range=None,
            tags=None,
            tag_match_mode=None,
            note_kinds=None,
            source_refs=None,
            limit=10,
            offset=0,
            sort=NoteSearchSort.created_at_desc,
        ),
    ) as api_client:
        response = await api_client.post("/api/message", json={"text": f"find {unique}"})

    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "search_notes"
    assert data["result"]["notes"]


@pytest.mark.asyncio
async def test_backend_search_tags_flow(memory_server_url: str):
    unique = uuid.uuid4().hex[:8]
    client = MemoryClient(memory_server_url)
    await client.open()
    try:
        await client.notes_save(
            {
                "raw_text": f"backend tags note {unique}",
                "normalized_text": f"backend tags note {unique}",
                "note_kind": "note",
                "created_at": "2024-01-01T00:00:00+00:00",
                "tags": [f"backend-tags-{unique}", "ai"],
                "source_ref": f"backend-tags-{unique}",
            }
        )
    finally:
        await client.close()

    async with _api_client(
        memory_server_url,
        intent=BackendIntent.search_tags,
        search_tags_input=TagSearchRequest(
            query=unique,
            time_range=None,
            note_kinds=None,
            source_refs=None,
            limit=10,
            offset=0,
            sort=TagSearchSort.usage_count_desc,
        ),
    ) as api_client:
        response = await api_client.post("/api/message", json={"text": f"какие теги по {unique}"})

    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "search_tags"
    assert data["result"]["tags"]


@pytest.mark.asyncio
async def test_backend_update_note_flow(memory_server_url: str):
    unique = uuid.uuid4().hex[:8]
    client = MemoryClient(memory_server_url)
    await client.open()
    try:
        saved = await client.notes_save(
            {
                "raw_text": f"backend update note {unique}",
                "normalized_text": f"backend update note {unique}",
                "note_kind": "note",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "tags": ["backend-update"],
                "source_ref": f"backend-update-{unique}",
            }
        )
    finally:
        await client.close()

    async with _api_client(
        memory_server_url,
        intent=BackendIntent.update_note,
        update_input=UpdateExtractionResult(
            target_mode=UpdateTargetMode.latest_note,
            operations=[
                {
                    "kind": "set_note_kind",
                    "note_kind": "task",
                }
            ],
        ),
    ) as api_client:
        response = await api_client.post("/api/message", json={"text": "исправь тип заметки на task"})

    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "update_note"
    assert data["result"]["note"]["id"] == saved["id"]
    assert data["result"]["note"]["note_kind"] == "task"
