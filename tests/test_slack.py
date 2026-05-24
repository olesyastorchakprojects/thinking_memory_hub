from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from backend.message_service import MessageService
from backend.models import BackendIntent, MessageResponse
from backend.server import build_app
from backend.slack import (
    SlackApiError,
    SlackClient,
    SlackEventHandler,
    SlackRequestError,
    SlackSignatureVerifier,
)


def _sign(secret: str, body: bytes, timestamp: str) -> str:
    base = f"v0:{timestamp}:{body.decode('utf-8')}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
    return f"v0={digest}"


def _signed_headers(secret: str, body: bytes, *, timestamp: str | None = None) -> dict[str, str]:
    ts = timestamp or str(int(time.time()))
    return {
        "x-slack-request-timestamp": ts,
        "x-slack-signature": _sign(secret, body, ts),
    }


def _message_service() -> MessageService:
    service = MagicMock(spec=MessageService)
    service.process_message = AsyncMock(
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
    return service


def test_slack_signature_verifier_accepts_valid_signature():
    body = b'{"type":"url_verification","challenge":"abc"}'
    headers = _signed_headers("secret", body)

    SlackSignatureVerifier("secret").verify(headers, body)


def test_slack_signature_verifier_rejects_invalid_signature():
    body = b"{}"
    headers = {
        "x-slack-request-timestamp": str(int(time.time())),
        "x-slack-signature": "v0=bad",
    }

    with pytest.raises(SlackRequestError):
        SlackSignatureVerifier("secret").verify(headers, body)


@pytest.mark.asyncio
async def test_slack_event_handler_handles_url_verification():
    secret = "secret"
    body = json.dumps({"type": "url_verification", "challenge": "abc"}).encode("utf-8")
    handler = SlackEventHandler(
        message_service=_message_service(),
        slack_client=MagicMock(spec=SlackClient),
        signature_verifier=SlackSignatureVerifier(secret),
    )

    result = await handler.handle(body=body, headers=_signed_headers(secret, body))

    assert result == {"challenge": "abc"}


@pytest.mark.asyncio
async def test_slack_event_handler_processes_app_mention():
    secret = "secret"
    body = json.dumps(
        {
            "type": "event_callback",
            "event": {
                "type": "app_mention",
                "text": "<@U123> чем отличаются prompts и resources",
                "channel": "C123",
                "ts": "1710000000.000100",
            },
        }
    ).encode("utf-8")
    message_service = _message_service()
    slack_client = MagicMock(spec=SlackClient)
    slack_client.post_message = AsyncMock()
    scheduled: list[asyncio.Task] = []
    handler = SlackEventHandler(
        message_service=message_service,
        slack_client=slack_client,
        signature_verifier=SlackSignatureVerifier(secret),
        schedule_background=scheduled.append,
    )

    result = await handler.handle(body=body, headers=_signed_headers(secret, body))
    await asyncio.gather(*scheduled)

    assert result == {"ok": True}
    message_service.process_message.assert_awaited_once()
    request = message_service.process_message.await_args.args[0]
    assert request.text == "чем отличаются prompts и resources"
    slack_client.post_message.assert_awaited_once_with(
        channel="C123",
        text="Note saved.",
        thread_ts="1710000000.000100",
    )


@pytest.mark.asyncio
async def test_slack_event_handler_deduplicates_event_id():
    secret = "secret"
    body = json.dumps(
        {
            "type": "event_callback",
            "event_id": "Ev123",
            "event": {
                "type": "app_mention",
                "text": "<@U123> hello",
                "channel": "C123",
                "ts": "1710000000.000100",
            },
        }
    ).encode("utf-8")
    message_service = _message_service()
    slack_client = MagicMock(spec=SlackClient)
    slack_client.post_message = AsyncMock()
    scheduled: list[asyncio.Task] = []
    handler = SlackEventHandler(
        message_service=message_service,
        slack_client=slack_client,
        signature_verifier=SlackSignatureVerifier(secret),
        schedule_background=scheduled.append,
    )

    first = await handler.handle(body=body, headers=_signed_headers(secret, body))
    await asyncio.gather(*scheduled)
    second = await handler.handle(body=body, headers=_signed_headers(secret, body))

    assert first == {"ok": True}
    assert second == {"ok": True}
    message_service.process_message.assert_awaited_once()
    slack_client.post_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_slack_client_raises_on_api_error():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"ok": False, "error": "invalid_auth"})
    )
    client = SlackClient(bot_token="xoxb-test", api_base_url="https://slack.test")
    client._http_client = httpx.AsyncClient(transport=transport)
    try:
        with pytest.raises(SlackApiError):
            await client.post_message(channel="C123", text="hello")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_slack_events_endpoint_invalid_signature_returns_401():
    service = _message_service()
    slack_client = MagicMock(spec=SlackClient)
    slack_client.post_message = AsyncMock()
    app: FastAPI = build_app(
        service,
        slack_event_handler=SlackEventHandler(
            message_service=service,
            slack_client=slack_client,
            signature_verifier=SlackSignatureVerifier("secret"),
        ),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/slack/events",
            content=b"{}",
            headers={
                "X-Slack-Request-Timestamp": str(int(time.time())),
                "X-Slack-Signature": "v0=bad",
            },
        )
    assert response.status_code == 401
