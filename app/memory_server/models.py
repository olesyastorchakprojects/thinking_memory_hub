from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class NoteKind(str, Enum):
    note = "note"
    question = "question"
    task = "task"
    reading = "reading"
    watch = "watch"


class TagMatchMode(str, Enum):
    any = "any"
    all = "all"


class NoteSearchSort(str, Enum):
    created_at_desc = "created_at_desc"
    created_at_asc = "created_at_asc"


class TagSearchSort(str, Enum):
    usage_count_desc = "usage_count_desc"
    name_asc = "name_asc"


class NoteUpdateOperationKind(str, Enum):
    set_note_kind = "set_note_kind"
    set_normalized_text = "set_normalized_text"
    replace_tags = "replace_tags"
    add_tags = "add_tags"
    remove_tags = "remove_tags"


class TimeRange(BaseModel):
    from_: datetime = Field(alias="from")
    to: datetime

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def validate_range(self) -> TimeRange:
        if self.from_ > self.to:
            raise ValueError("from must be less than or equal to to")
        return self


class NoteRecord(BaseModel):
    id: UUID
    raw_text: Annotated[str, Field(min_length=1)]
    normalized_text: Annotated[str, Field(min_length=1)]
    note_kind: NoteKind
    source_ref: str | None = None
    created_at: datetime
    updated_at: datetime
    tags: list[str]

    @field_validator("source_ref")
    @classmethod
    def source_ref_non_empty(cls, v: str | None) -> str | None:
        if v is not None and v == "":
            raise ValueError("source_ref must be non-empty when present")
        return v

    @field_validator("tags")
    @classmethod
    def tags_non_empty_values(cls, v: list[str]) -> list[str]:
        for tag in v:
            if tag == "":
                raise ValueError("tag values must be non-empty")
        return v


class NoteCreateRequest(BaseModel):
    raw_text: Annotated[str, Field(min_length=1)]
    normalized_text: Annotated[str, Field(min_length=1)]
    note_kind: NoteKind
    source_ref: str | None = None
    created_at: datetime
    tags: list[str]

    @field_validator("source_ref")
    @classmethod
    def source_ref_non_empty(cls, v: str | None) -> str | None:
        if v is not None and v == "":
            raise ValueError("source_ref must be non-empty when present")
        return v

    @field_validator("tags")
    @classmethod
    def tags_non_empty_values(cls, v: list[str]) -> list[str]:
        for tag in v:
            if tag == "":
                raise ValueError("tag values must be non-empty")
        return v


class NoteSearchRequest(BaseModel):
    query: str | None = None
    time_range: TimeRange | None = None
    tags: list[str] | None = None
    tag_match_mode: TagMatchMode | None = None
    note_kinds: list[NoteKind] | None = None
    source_refs: list[str] | None = None
    limit: Annotated[int, Field(gt=0)]
    offset: Annotated[int, Field(ge=0)]
    sort: NoteSearchSort


class TagSearchRequest(BaseModel):
    query: str | None = None
    time_range: TimeRange | None = None
    note_kinds: list[NoteKind] | None = None
    source_refs: list[str] | None = None
    limit: Annotated[int, Field(gt=0)]
    offset: Annotated[int, Field(ge=0)]
    sort: TagSearchSort


class SetNoteKindOperation(BaseModel):
    kind: Literal[NoteUpdateOperationKind.set_note_kind] = NoteUpdateOperationKind.set_note_kind
    note_kind: NoteKind

    model_config = {"frozen": True}


class SetNormalizedTextOperation(BaseModel):
    kind: Literal[NoteUpdateOperationKind.set_normalized_text] = NoteUpdateOperationKind.set_normalized_text
    normalized_text: Annotated[str, Field(min_length=1)]

    model_config = {"frozen": True}


class ReplaceTagsOperation(BaseModel):
    kind: Literal[NoteUpdateOperationKind.replace_tags] = NoteUpdateOperationKind.replace_tags
    tags: list[str]

    model_config = {"frozen": True}

    @field_validator("tags")
    @classmethod
    def tags_non_empty_values(cls, v: list[str]) -> list[str]:
        for tag in v:
            if tag == "":
                raise ValueError("tag values must be non-empty")
        return v


class AddTagsOperation(BaseModel):
    kind: Literal[NoteUpdateOperationKind.add_tags] = NoteUpdateOperationKind.add_tags
    tags: list[str]

    model_config = {"frozen": True}

    @field_validator("tags")
    @classmethod
    def tags_non_empty_values(cls, v: list[str]) -> list[str]:
        for tag in v:
            if tag == "":
                raise ValueError("tag values must be non-empty")
        return v


class RemoveTagsOperation(BaseModel):
    kind: Literal[NoteUpdateOperationKind.remove_tags] = NoteUpdateOperationKind.remove_tags
    tags: list[str]

    model_config = {"frozen": True}

    @field_validator("tags")
    @classmethod
    def tags_non_empty_values(cls, v: list[str]) -> list[str]:
        for tag in v:
            if tag == "":
                raise ValueError("tag values must be non-empty")
        return v


NoteUpdateOperation = Annotated[
    Union[
        SetNoteKindOperation,
        SetNormalizedTextOperation,
        ReplaceTagsOperation,
        AddTagsOperation,
        RemoveTagsOperation,
    ],
    Field(discriminator="kind"),
]


class NoteUpdateRequest(BaseModel):
    note_id: UUID
    operations: Annotated[list[NoteUpdateOperation], Field(min_length=1)]


class NoteList(BaseModel):
    items: list[NoteRecord]


class TagSearchResult(BaseModel):
    name: Annotated[str, Field(min_length=1)]
    usage_count: Annotated[int, Field(ge=0)]


class TagList(BaseModel):
    items: list[TagSearchResult]
