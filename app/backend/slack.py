from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import re
import time
from collections.abc import Awaitable, Callable, Mapping

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.errors import (
    BackendProcessingError,
    IntentParseError,
    MemoryServerError,
    SlackApiError,
    SlackRequestError,
)
from backend.message_service import MessageService
from backend.models import BackendIntent, MessageRequest, MessageResponse

_MENTION_RE = re.compile(r"^(\s*<@[^>]+>\s*)+")


class SlackSignatureVerifier:
    def __init__(self, signing_secret: str, *, tolerance_sec: int = 300) -> None:
        self._signing_secret = signing_secret.encode("utf-8")
        self._tolerance_sec = tolerance_sec

    def verify(self, headers: Mapping[str, str], body: bytes) -> None:
        timestamp = headers.get("x-slack-request-timestamp")
        signature = headers.get("x-slack-signature")
        if not timestamp or not signature:
            raise SlackRequestError("Missing Slack signature headers")

        try:
            timestamp_int = int(timestamp)
        except ValueError as exc:
            raise SlackRequestError("Invalid Slack timestamp header") from exc

        if abs(int(time.time()) - timestamp_int) > self._tolerance_sec:
            raise SlackRequestError("Slack request timestamp is outside the accepted window")

        signed = f"v0:{timestamp}:{body.decode('utf-8')}".encode("utf-8")
        digest = hmac.new(self._signing_secret, signed, hashlib.sha256).hexdigest()
        expected = f"v0={digest}"
        if not hmac.compare_digest(expected, signature):
            raise SlackRequestError("Slack request signature is invalid")


class SlackClient:
    def __init__(
        self,
        *,
        bot_token: str,
        api_base_url: str = "https://slack.com/api",
        timeout_sec: int = 15,
    ) -> None:
        self._bot_token = bot_token
        self._api_base_url = api_base_url.rstrip("/")
        self._http_client = httpx.AsyncClient(timeout=timeout_sec)

    async def close(self) -> None:
        await self._http_client.aclose()

    async def post_message(self, *, channel: str, text: str, thread_ts: str | None = None) -> None:
        payload: dict[str, str] = {
            "channel": channel,
            "text": text,
        }
        if thread_ts is not None:
            payload["thread_ts"] = thread_ts

        try:
            response = await self._http_client.post(
                f"{self._api_base_url}/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {self._bot_token}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                json=payload,
            )
        except Exception as exc:
            raise SlackApiError("Slack transport failure") from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise SlackApiError(f"Slack API returned HTTP {response.status_code}")

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise SlackApiError("Slack API returned invalid JSON") from exc

        if not data.get("ok"):
            raise SlackApiError(f"Slack API error: {data.get('error', 'unknown_error')}")


class SlackEventHandler:
    def __init__(
        self,
        *,
        message_service: MessageService,
        slack_client: SlackClient,
        signature_verifier: SlackSignatureVerifier,
        schedule_background: Callable[[Awaitable[None]], object] | None = None,
        dedupe_ttl_sec: int = 600,
    ) -> None:
        self._message_service = message_service
        self._slack_client = slack_client
        self._signature_verifier = signature_verifier
        self._schedule_background = schedule_background or asyncio.create_task
        self._dedupe_ttl_sec = dedupe_ttl_sec
        self._seen_event_ids: dict[str, float] = {}

    async def handle(self, *, body: bytes, headers: Mapping[str, str]) -> dict:
        self._signature_verifier.verify(headers, body)
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise SlackRequestError("Slack request body is not valid JSON") from exc

        if payload.get("type") == "url_verification":
            challenge = payload.get("challenge")
            if not isinstance(challenge, str) or not challenge:
                raise SlackRequestError("Slack challenge payload is invalid")
            return {"challenge": challenge}

        if payload.get("type") != "event_callback":
            return {"ok": True}

        event_id = payload.get("event_id")
        if isinstance(event_id, str) and event_id:
            if self._is_duplicate_event(event_id):
                return {"ok": True}
            self._remember_event(event_id)

        event = payload.get("event") or {}
        if event.get("type") != "app_mention":
            return {"ok": True}
        if event.get("subtype") == "bot_message":
            return {"ok": True}

        raw_text = event.get("text")
        channel = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")
        if not isinstance(raw_text, str) or not isinstance(channel, str):
            raise SlackRequestError("Slack app_mention event is missing text or channel")

        user_text = _MENTION_RE.sub("", raw_text).strip()
        if not user_text:
            self._schedule_background(
                self._slack_client.post_message(
                    channel=channel,
                    text="Please send a message after mentioning me.",
                    thread_ts=thread_ts,
                )
            )
            return {"ok": True}

        self._schedule_background(
            self._process_app_mention(
                user_text=user_text,
                channel=channel,
                thread_ts=thread_ts,
            )
        )
        return {"ok": True}

    async def _process_app_mention(
        self,
        *,
        user_text: str,
        channel: str,
        thread_ts: str | None,
    ) -> None:
        try:
            response = await self._message_service.process_message(MessageRequest(text=user_text))
            reply_text = _format_slack_reply(response)
        except (IntentParseError, BackendProcessingError, MemoryServerError) as exc:
            reply_text = f"Sorry, I couldn't process that message: {exc}"

        await self._slack_client.post_message(
            channel=channel,
            text=reply_text,
            thread_ts=thread_ts,
        )

    def _is_duplicate_event(self, event_id: str) -> bool:
        self._prune_seen_event_ids()
        return event_id in self._seen_event_ids

    def _remember_event(self, event_id: str) -> None:
        self._prune_seen_event_ids()
        self._seen_event_ids[event_id] = time.time()

    def _prune_seen_event_ids(self) -> None:
        cutoff = time.time() - self._dedupe_ttl_sec
        stale = [event_id for event_id, seen_at in self._seen_event_ids.items() if seen_at < cutoff]
        for event_id in stale:
            del self._seen_event_ids[event_id]


def create_slack_router(handler: SlackEventHandler) -> APIRouter:
    router = APIRouter()

    @router.post("/slack/events")
    async def post_slack_events(request: Request):
        body = await request.body()
        headers = {key.lower(): value for key, value in request.headers.items()}
        try:
            payload = await handler.handle(body=body, headers=headers)
        except SlackRequestError as exc:
            return JSONResponse(status_code=401, content={"error": str(exc)})
        except SlackApiError as exc:
            return JSONResponse(status_code=502, content={"error": str(exc)})
        return JSONResponse(status_code=200, content=payload)

    return router


def _format_slack_reply(response: MessageResponse) -> str:
    if response.intent == BackendIntent.search_notes:
        notes = response.result.notes[:5]  # type: ignore[union-attr]
        if not notes:
            return "Found 0 notes."
        lines = [response.message]
        lines.extend(f"- {note.raw_text}" for note in notes)
        return "\n".join(lines)
    if response.intent == BackendIntent.search_tags:
        tags = response.result.tags[:10]  # type: ignore[union-attr]
        if not tags:
            return "Found 0 tags."
        lines = [response.message]
        lines.extend(f"- {tag.name} ({tag.usage_count})" for tag in tags)
        return "\n".join(lines)
    return response.message
