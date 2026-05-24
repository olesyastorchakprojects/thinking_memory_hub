from __future__ import annotations

import json
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import TextContent

from backend.errors import MemoryServerError


class MemoryClient:
    def __init__(self, memory_server_url: str) -> None:
        self._memory_server_url = memory_server_url
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def open(self) -> None:
        if self._session is not None:
            return
        stack = AsyncExitStack()
        try:
            read_stream, write_stream, _ = await stack.enter_async_context(
                streamable_http_client(self._memory_server_url)
            )
            session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
            await session.initialize()
        except Exception:
            await stack.aclose()
            raise
        self._stack = stack
        self._session = session

    async def close(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._session = None

    async def notes_save(self, request: dict) -> dict:
        return await self._call_tool("notes.save", request)

    async def notes_search(self, request: dict) -> dict:
        return await self._call_tool("notes.search", request)

    async def notes_update(self, request: dict) -> dict:
        return await self._call_tool("notes.update", request)

    async def tags_search(self, request: dict) -> dict:
        return await self._call_tool("tags.search", request)

    async def _call_tool(self, tool_name: str, arguments: dict) -> dict:
        session = self._require_session()
        try:
            result = await session.call_tool(tool_name, arguments)
        except Exception as exc:
            raise MemoryServerError(f"Remote MCP call failed for {tool_name!r}") from exc

        payload = self._extract_payload(result)
        if payload is None:
            raise MemoryServerError(f"Remote MCP call returned no structured payload for {tool_name!r}")
        if not isinstance(payload, dict):
            raise MemoryServerError(
                f"Remote MCP call returned non-dict payload for {tool_name!r}: {payload!r}"
            )
        return payload

    def _require_session(self) -> ClientSession:
        if self._session is None:
            raise MemoryServerError("MemoryClient is not open")
        return self._session

    @staticmethod
    def _extract_payload(result) -> dict | None:
        structured = getattr(result, "structuredContent", None)
        if structured is not None:
            return structured
        content = getattr(result, "content", None)
        if content and isinstance(content[0], TextContent):
            try:
                return json.loads(content[0].text)
            except json.JSONDecodeError as exc:
                raise MemoryServerError("Failed to decode text tool result as JSON") from exc
        return None

