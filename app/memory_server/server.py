from __future__ import annotations

import logging
from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from memory_server.mcp_tools import (
    handle_notes_save,
    handle_notes_search,
    handle_notes_update,
    handle_tags_search,
)
from memory_server.models import (
    NoteKind,
    NoteList,
    NoteRecord,
    NoteSearchSort,
    NoteUpdateOperation,
    TagList,
    TagMatchMode,
    TagSearchSort,
    TimeRange,
)
from memory_server.storage_client import StorageClient

_NonEmptyStr = Annotated[str, Field(min_length=1)]
logger = logging.getLogger(__name__)


def build_server(storage_client: StorageClient) -> FastMCP:
    logger.info("Creating FastMCP instance")
    mcp = FastMCP("thinking-memory-hub")

    @mcp.tool(name="notes.save", description="Save one note record.")
    async def notes_save(
        raw_text: _NonEmptyStr,
        normalized_text: _NonEmptyStr,
        note_kind: NoteKind,
        created_at: str,
        tags: list[_NonEmptyStr],
        source_ref: Optional[_NonEmptyStr] = None,
    ) -> NoteRecord:
        result = await handle_notes_save(
            {
                "raw_text": raw_text,
                "normalized_text": normalized_text,
                "note_kind": note_kind,
                "created_at": created_at,
                "tags": tags,
                "source_ref": source_ref,
            },
            storage_client,
        )
        return NoteRecord.model_validate(result)

    @mcp.tool(name="notes.search", description="Search note records by query and filters.")
    async def notes_search(
        limit: Annotated[int, Field(gt=0)],
        offset: Annotated[int, Field(ge=0)],
        sort: NoteSearchSort,
        query: Optional[str] = None,
        time_range: Optional[TimeRange] = None,
        tags: Optional[list[_NonEmptyStr]] = None,
        tag_match_mode: Optional[TagMatchMode] = None,
        note_kinds: Optional[list[NoteKind]] = None,
        source_refs: Optional[list[_NonEmptyStr]] = None,
    ) -> NoteList:
        result = await handle_notes_search(
            {
                "query": query,
                "time_range": time_range.model_dump(by_alias=True) if time_range is not None else None,
                "tags": tags,
                "tag_match_mode": tag_match_mode,
                "note_kinds": note_kinds,
                "source_refs": source_refs,
                "limit": limit,
                "offset": offset,
                "sort": sort,
            },
            storage_client,
        )
        return NoteList.model_validate(result)

    @mcp.tool(name="notes.update", description="Update one existing note record.")
    async def notes_update(
        note_id: str,
        operations: Annotated[list[NoteUpdateOperation], Field(min_length=1)],
    ) -> NoteRecord:
        result = await handle_notes_update(
            {
                "note_id": note_id,
                "operations": [op.model_dump() for op in operations],
            },
            storage_client,
        )
        return NoteRecord.model_validate(result)

    @mcp.tool(name="tags.search", description="Search aggregated tags derived from matching notes.")
    async def tags_search(
        limit: Annotated[int, Field(gt=0)],
        offset: Annotated[int, Field(ge=0)],
        sort: TagSearchSort,
        query: Optional[str] = None,
        time_range: Optional[TimeRange] = None,
        note_kinds: Optional[list[NoteKind]] = None,
        source_refs: Optional[list[_NonEmptyStr]] = None,
    ) -> TagList:
        result = await handle_tags_search(
            {
                "query": query,
                "time_range": time_range.model_dump(by_alias=True) if time_range is not None else None,
                "note_kinds": note_kinds,
                "source_refs": source_refs,
                "limit": limit,
                "offset": offset,
                "sort": sort,
            },
            storage_client,
        )
        return TagList.model_validate(result)

    logger.info("FastMCP instance created and tools registered")
    return mcp
