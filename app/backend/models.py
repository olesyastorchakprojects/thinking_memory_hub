from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Union

from pydantic import BaseModel, Field

from memory_server.models import NoteRecord, NoteUpdateOperation, TagSearchResult


class BackendIntent(str, Enum):
    save_note = "save_note"
    search_notes = "search_notes"
    search_tags = "search_tags"
    update_note = "update_note"


class BackendErrorCode(str, Enum):
    invalid_request = "invalid_request"
    intent_parse_failed = "intent_parse_failed"
    backend_processing_failed = "backend_processing_failed"
    memory_server_error = "memory_server_error"


class ClassifierConfidence(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class UpdateTargetMode(str, Enum):
    latest_note = "latest_note"
    unresolved = "unresolved"


class HealthResponse(BaseModel):
    status: str = Field(default="ok")

    @classmethod
    def ok(cls) -> "HealthResponse":
        return cls(status="ok")


class MessageRequest(BaseModel):
    text: Annotated[str, Field(min_length=1)]


class SaveNoteResult(BaseModel):
    note: NoteRecord


class SearchNotesResult(BaseModel):
    notes: list[NoteRecord]


class SearchTagsResult(BaseModel):
    tags: list[TagSearchResult]


class UpdateNoteResult(BaseModel):
    note: NoteRecord


MessageResult = Union[
    SaveNoteResult,
    SearchNotesResult,
    SearchTagsResult,
    UpdateNoteResult,
]


class MessageResponse(BaseModel):
    message: Annotated[str, Field(min_length=1)]
    intent: BackendIntent
    result: MessageResult


class ErrorBody(BaseModel):
    code: BackendErrorCode
    message: Annotated[str, Field(min_length=1)]


class ErrorResponse(BaseModel):
    error: ErrorBody


class ModelMessageRole(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"


class ModelMessage(BaseModel):
    role: ModelMessageRole
    content: Annotated[str, Field(min_length=1)]


class ModelGenerationRequest(BaseModel):
    messages: Annotated[list[ModelMessage], Field(min_length=1)]
    temperature: Annotated[float, Field(ge=0.0)]
    max_output_tokens: Annotated[int | None, Field(gt=0)] = None
    response_schema: dict[str, Any]


class ModelGenerationResponse(BaseModel):
    content: Annotated[str, Field(min_length=1)]
    finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    input_cost: float | None = None
    output_cost: float | None = None


class IntentClassificationResult(BaseModel):
    intent: BackendIntent
    reason: Annotated[str, Field(min_length=1)]
    confidence: ClassifierConfidence


class SaveExtractionResult(BaseModel):
    raw_text: Annotated[str, Field(min_length=1)]
    normalized_text: Annotated[str, Field(min_length=1)]
    note_kind: NoteRecord.model_fields["note_kind"].annotation
    tags: list[str]
    source_ref: str | None = None


class UpdateExtractionResult(BaseModel):
    target_mode: UpdateTargetMode
    operations: Annotated[list[NoteUpdateOperation], Field(min_length=1)]
