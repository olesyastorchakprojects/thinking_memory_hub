from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from backend.api import create_api_router
from backend.models import BackendIntent, MessageResponse


def _build_app(message_service) -> FastAPI:
    app = FastAPI()
    app.include_router(create_api_router(message_service))
    return app


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = httpx.ASGITransport(app=_build_app(MagicMock()))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_message_endpoint_success():
    message_service = MagicMock()
    message_service.process_message = AsyncMock(
        return_value=MessageResponse(
            message="Note saved.",
            intent=BackendIntent.save_note,
            result={
                "note": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "raw_text": "raw",
                    "normalized_text": "normalized",
                    "note_kind": "note",
                    "source_ref": None,
                    "created_at": "2024-01-01T00:00:00+00:00",
                    "updated_at": "2024-01-01T00:00:00+00:00",
                    "tags": [],
                }
            },
        )
    )
    transport = httpx.ASGITransport(app=_build_app(message_service))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/message", json={"text": "save raw"})
    assert response.status_code == 200
    assert response.json()["intent"] == "save_note"


@pytest.mark.asyncio
async def test_message_endpoint_invalid_request():
    transport = httpx.ASGITransport(app=_build_app(MagicMock()))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/message", json={"text": ""})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"
