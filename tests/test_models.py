from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from memory_server.models import (
    AddTagsOperation,
    NoteCreateRequest,
    NoteKind,
    NoteList,
    NoteRecord,
    NoteSearchRequest,
    NoteSearchSort,
    NoteUpdateOperation,
    NoteUpdateOperationKind,
    NoteUpdateRequest,
    RemoveTagsOperation,
    ReplaceTagsOperation,
    SetNoteKindOperation,
    SetNormalizedTextOperation,
    TagList,
    TagMatchMode,
    TagSearchRequest,
    TagSearchResult,
    TagSearchSort,
    TimeRange,
)

NOW = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
LATER = datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc)


# ── TimeRange ────────────────────────────────────────────────────────────────


def test_time_range_valid():
    tr = TimeRange(**{"from": NOW, "to": LATER})
    assert tr.from_ == NOW
    assert tr.to == LATER


def test_time_range_equal_bounds():
    tr = TimeRange(**{"from": NOW, "to": NOW})
    assert tr.from_ == tr.to


def test_time_range_invalid():
    with pytest.raises(ValidationError):
        TimeRange(**{"from": LATER, "to": NOW})


# ── NoteRecord ───────────────────────────────────────────────────────────────


def test_note_record_valid():
    record = NoteRecord(
        id=uuid4(),
        raw_text="hello",
        normalized_text="hello normalized",
        note_kind=NoteKind.note,
        source_ref=None,
        created_at=NOW,
        updated_at=NOW,
        tags=["a", "b"],
    )
    assert record.note_kind == NoteKind.note
    assert record.tags == ["a", "b"]


def test_note_record_empty_raw_text():
    with pytest.raises(ValidationError):
        NoteRecord(
            id=uuid4(),
            raw_text="",
            normalized_text="x",
            note_kind=NoteKind.note,
            created_at=NOW,
            updated_at=NOW,
            tags=[],
        )


def test_note_record_empty_normalized_text():
    with pytest.raises(ValidationError):
        NoteRecord(
            id=uuid4(),
            raw_text="x",
            normalized_text="",
            note_kind=NoteKind.note,
            created_at=NOW,
            updated_at=NOW,
            tags=[],
        )


def test_note_record_empty_source_ref():
    with pytest.raises(ValidationError):
        NoteRecord(
            id=uuid4(),
            raw_text="x",
            normalized_text="x",
            note_kind=NoteKind.note,
            source_ref="",
            created_at=NOW,
            updated_at=NOW,
            tags=[],
        )


def test_note_record_empty_tag_value():
    with pytest.raises(ValidationError):
        NoteRecord(
            id=uuid4(),
            raw_text="x",
            normalized_text="x",
            note_kind=NoteKind.note,
            created_at=NOW,
            updated_at=NOW,
            tags=[""],
        )


# ── NoteCreateRequest ────────────────────────────────────────────────────────


def test_note_create_request_valid():
    req = NoteCreateRequest(
        raw_text="hello",
        normalized_text="hello norm",
        note_kind=NoteKind.task,
        source_ref="ref-1",
        created_at=NOW,
        tags=["python"],
    )
    assert req.note_kind == NoteKind.task


def test_note_create_request_invalid_note_kind():
    with pytest.raises(ValidationError):
        NoteCreateRequest(
            raw_text="x",
            normalized_text="x",
            note_kind="invalid_kind",
            created_at=NOW,
            tags=[],
        )


def test_note_create_request_empty_normalized_text():
    with pytest.raises(ValidationError):
        NoteCreateRequest(
            raw_text="x",
            normalized_text="",
            note_kind=NoteKind.note,
            created_at=NOW,
            tags=[],
        )


# ── NoteSearchRequest ────────────────────────────────────────────────────────


def test_note_search_request_valid_minimal():
    req = NoteSearchRequest(limit=10, offset=0, sort=NoteSearchSort.created_at_desc)
    assert req.query is None
    assert req.tags is None


def test_note_search_request_invalid_limit():
    with pytest.raises(ValidationError):
        NoteSearchRequest(limit=0, offset=0, sort=NoteSearchSort.created_at_desc)


def test_note_search_request_invalid_sort():
    with pytest.raises(ValidationError):
        NoteSearchRequest(limit=10, offset=0, sort="bad_sort")


# ── TagSearchRequest ─────────────────────────────────────────────────────────


def test_tag_search_request_valid():
    req = TagSearchRequest(limit=5, offset=0, sort=TagSearchSort.name_asc)
    assert req.query is None


def test_tag_search_request_invalid_sort():
    with pytest.raises(ValidationError):
        TagSearchRequest(limit=5, offset=0, sort="nope")


# ── NoteUpdateOperation tagged union ─────────────────────────────────────────


def test_set_note_kind_operation():
    op = SetNoteKindOperation(kind=NoteUpdateOperationKind.set_note_kind, note_kind=NoteKind.task)
    assert op.kind == NoteUpdateOperationKind.set_note_kind


def test_set_normalized_text_operation():
    op = SetNormalizedTextOperation(
        kind=NoteUpdateOperationKind.set_normalized_text, normalized_text="new text"
    )
    assert op.normalized_text == "new text"


def test_set_normalized_text_empty_rejected():
    with pytest.raises(ValidationError):
        SetNormalizedTextOperation(
            kind=NoteUpdateOperationKind.set_normalized_text, normalized_text=""
        )


def test_replace_tags_operation():
    op = ReplaceTagsOperation(kind=NoteUpdateOperationKind.replace_tags, tags=["x"])
    assert op.tags == ["x"]


def test_add_tags_operation():
    op = AddTagsOperation(kind=NoteUpdateOperationKind.add_tags, tags=["y"])
    assert op.tags == ["y"]


def test_remove_tags_operation():
    op = RemoveTagsOperation(kind=NoteUpdateOperationKind.remove_tags, tags=["z"])
    assert op.tags == ["z"]


def test_note_update_request_valid():
    req = NoteUpdateRequest(
        note_id=uuid4(),
        operations=[{"kind": "set_note_kind", "note_kind": "task"}],
    )
    assert len(req.operations) == 1


def test_note_update_request_empty_operations():
    with pytest.raises(ValidationError):
        NoteUpdateRequest(note_id=uuid4(), operations=[])


def test_note_update_operation_invalid_kind():
    with pytest.raises(ValidationError):
        NoteUpdateRequest(
            note_id=uuid4(),
            operations=[{"kind": "nonexistent_kind", "value": "x"}],
        )


# ── NoteList / TagList ────────────────────────────────────────────────────────


def test_note_list_empty():
    nl = NoteList(items=[])
    assert nl.items == []


def test_tag_list_items():
    tl = TagList(items=[TagSearchResult(name="python", usage_count=3)])
    assert tl.items[0].usage_count == 3


def test_tag_search_result_invalid_usage_count():
    with pytest.raises(ValidationError):
        TagSearchResult(name="x", usage_count=-1)


def test_tag_search_result_empty_name():
    with pytest.raises(ValidationError):
        TagSearchResult(name="", usage_count=0)
