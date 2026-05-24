from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.models import (
    BackendErrorCode,
    BackendIntent,
    ErrorBody,
    ErrorResponse,
    HealthResponse,
    MessageRequest,
    MessageResponse,
    SaveNoteResult,
    SearchNotesResult,
    SearchTagsResult,
    UpdateExtractionResult,
    UpdateTargetMode,
    UpdateNoteResult,
)
from memory_server.models import NoteKind, NoteRecord, TagSearchResult

NOW = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _note_record() -> NoteRecord:
    return NoteRecord(
        id=uuid4(),
        raw_text="raw",
        normalized_text="normalized",
        note_kind=NoteKind.note,
        created_at=NOW,
        updated_at=NOW,
        tags=[],
    )


def test_health_response_ok():
    assert HealthResponse.ok().status == "ok"


def test_message_request_requires_non_empty_text():
    with pytest.raises(ValidationError):
        MessageRequest(text="")


def test_save_note_result_valid():
    result = SaveNoteResult(note=_note_record())
    assert result.note.note_kind == NoteKind.note


def test_search_notes_result_valid():
    result = SearchNotesResult(notes=[_note_record()])
    assert len(result.notes) == 1


def test_search_tags_result_valid():
    result = SearchTagsResult(tags=[TagSearchResult(name="mcp", usage_count=2)])
    assert result.tags[0].name == "mcp"


def test_update_note_result_valid():
    result = UpdateNoteResult(note=_note_record())
    assert result.note.raw_text == "raw"


def test_message_response_with_save_result():
    response = MessageResponse(
        message="saved",
        intent=BackendIntent.save_note,
        result=SaveNoteResult(note=_note_record()),
    )
    assert response.intent == BackendIntent.save_note


def test_update_extraction_result_valid_latest_note():
    result = UpdateExtractionResult(
        target_mode=UpdateTargetMode.latest_note,
        operations=[{"kind": "set_note_kind", "note_kind": "task"}],
    )
    assert result.target_mode == UpdateTargetMode.latest_note


def test_update_extraction_result_valid_unresolved():
    result = UpdateExtractionResult(
        target_mode=UpdateTargetMode.unresolved,
        operations=[{"kind": "set_note_kind", "note_kind": "task"}],
    )
    assert result.target_mode == UpdateTargetMode.unresolved


def test_error_response_valid():
    response = ErrorResponse(
        error=ErrorBody(code=BackendErrorCode.invalid_request, message="bad request")
    )
    assert response.error.code == BackendErrorCode.invalid_request
