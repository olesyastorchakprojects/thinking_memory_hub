from __future__ import annotations

from pydantic import ValidationError

from memory_server.errors import ToolInputValidationError
from memory_server.models import (
    NoteCreateRequest,
    NoteList,
    NoteRecord,
    NoteSearchRequest,
    NoteUpdateRequest,
    TagList,
    TagSearchRequest,
)
from memory_server.storage_client import StorageClient


async def handle_notes_save(arguments: dict, storage_client: StorageClient) -> dict:
    try:
        request = NoteCreateRequest.model_validate(arguments)
    except ValidationError as exc:
        raise ToolInputValidationError(str(exc)) from exc
    result: NoteRecord = await storage_client.create_note(request)
    return result.model_dump(mode="json")


async def handle_notes_search(arguments: dict, storage_client: StorageClient) -> dict:
    try:
        request = NoteSearchRequest.model_validate(arguments)
    except ValidationError as exc:
        raise ToolInputValidationError(str(exc)) from exc
    result: NoteList = await storage_client.search_notes(request)
    return result.model_dump(mode="json")


async def handle_notes_update(arguments: dict, storage_client: StorageClient) -> dict:
    try:
        request = NoteUpdateRequest.model_validate(arguments)
    except ValidationError as exc:
        raise ToolInputValidationError(str(exc)) from exc
    result: NoteRecord = await storage_client.update_note(request)
    return result.model_dump(mode="json")


async def handle_tags_search(arguments: dict, storage_client: StorageClient) -> dict:
    try:
        request = TagSearchRequest.model_validate(arguments)
    except ValidationError as exc:
        raise ToolInputValidationError(str(exc)) from exc
    result: TagList = await storage_client.search_tags(request)
    return result.model_dump(mode="json")
