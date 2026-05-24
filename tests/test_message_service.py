from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.errors import BackendProcessingError, IntentParseError
from backend.message_service import MessageService
from backend.models import (
    BackendIntent,
    ClassifierConfidence,
    IntentClassificationResult,
    MessageRequest,
)
from memory_server.models import (
    NoteCreateRequest,
    NoteSearchRequest,
    NoteSearchSort,
    NoteUpdateOperationKind,
    TagSearchRequest,
    TagSearchSort,
)
from backend.models import UpdateExtractionResult, UpdateTargetMode


def _service(
    *,
    classifier_result: IntentClassificationResult | Exception,
    save_input: NoteCreateRequest | Exception | None = None,
    search_input: NoteSearchRequest | Exception | None = None,
    search_tags_input: TagSearchRequest | Exception | None = None,
    update_input: UpdateExtractionResult | Exception | None = None,
    save_graph_state: dict | Exception | None = None,
    search_graph_state: dict | Exception | None = None,
    search_tags_graph_state: dict | Exception | None = None,
    update_graph_state: dict | Exception | None = None,
) -> tuple[MessageService, AsyncMock, AsyncMock, AsyncMock, AsyncMock, MagicMock, MagicMock, MagicMock, MagicMock]:
    intent_classifier = MagicMock()
    input_extractor = MagicMock()
    save_graph = MagicMock()
    search_graph = MagicMock()
    search_tags_graph = MagicMock()
    update_graph = MagicMock()

    intent_classifier.classify = AsyncMock(
        side_effect=classifier_result if isinstance(classifier_result, Exception) else None
    )
    if not isinstance(classifier_result, Exception):
        intent_classifier.classify.return_value = classifier_result

    input_extractor.extract_save_input = AsyncMock(
        side_effect=save_input if isinstance(save_input, Exception) else None
    )
    if save_input is not None and not isinstance(save_input, Exception):
        input_extractor.extract_save_input.return_value = save_input

    input_extractor.extract_search_notes_input = AsyncMock(
        side_effect=search_input if isinstance(search_input, Exception) else None
    )
    if search_input is not None and not isinstance(search_input, Exception):
        input_extractor.extract_search_notes_input.return_value = search_input

    input_extractor.extract_search_tags_input = AsyncMock(
        side_effect=search_tags_input if isinstance(search_tags_input, Exception) else None
    )
    if search_tags_input is not None and not isinstance(search_tags_input, Exception):
        input_extractor.extract_search_tags_input.return_value = search_tags_input

    input_extractor.extract_update_note_input = AsyncMock(
        side_effect=update_input if isinstance(update_input, Exception) else None
    )
    if update_input is not None and not isinstance(update_input, Exception):
        input_extractor.extract_update_note_input.return_value = update_input

    save_graph.ainvoke = AsyncMock(
        side_effect=save_graph_state if isinstance(save_graph_state, Exception) else None
    )
    if save_graph_state is not None and not isinstance(save_graph_state, Exception):
        save_graph.ainvoke.return_value = save_graph_state

    search_graph.ainvoke = AsyncMock(
        side_effect=search_graph_state if isinstance(search_graph_state, Exception) else None
    )
    if search_graph_state is not None and not isinstance(search_graph_state, Exception):
        search_graph.ainvoke.return_value = search_graph_state

    search_tags_graph.ainvoke = AsyncMock(
        side_effect=search_tags_graph_state
        if isinstance(search_tags_graph_state, Exception)
        else None
    )
    if search_tags_graph_state is not None and not isinstance(search_tags_graph_state, Exception):
        search_tags_graph.ainvoke.return_value = search_tags_graph_state

    update_graph.ainvoke = AsyncMock(
        side_effect=update_graph_state if isinstance(update_graph_state, Exception) else None
    )
    if update_graph_state is not None and not isinstance(update_graph_state, Exception):
        update_graph.ainvoke.return_value = update_graph_state

    service = MessageService(
        memory_client=object(),  # type: ignore[arg-type]
        intent_classifier=intent_classifier,
        input_extractor=input_extractor,
        save_graph=save_graph,
        search_notes_graph=search_graph,
        search_tags_graph=search_tags_graph,
        update_note_graph=update_graph,
    )
    return (
        service,
        intent_classifier.classify,
        input_extractor.extract_save_input,
        input_extractor.extract_search_tags_input,
        input_extractor.extract_update_note_input,
        save_graph,
        search_graph,
        search_tags_graph,
        update_graph,
    )


def _save_classification() -> IntentClassificationResult:
    return IntentClassificationResult(
        intent=BackendIntent.save_note,
        reason="Standalone thought defaults to save.",
        confidence=ClassifierConfidence.high,
    )


def _search_classification() -> IntentClassificationResult:
    return IntentClassificationResult(
        intent=BackendIntent.search_notes,
        reason="The message asks to view saved notes.",
        confidence=ClassifierConfidence.high,
    )


def _tags_classification() -> IntentClassificationResult:
    return IntentClassificationResult(
        intent=BackendIntent.search_tags,
        reason="The message asks about directions and tags.",
        confidence=ClassifierConfidence.medium,
    )


def _update_classification() -> IntentClassificationResult:
    return IntentClassificationResult(
        intent=BackendIntent.update_note,
        reason="The message asks to modify an existing note.",
        confidence=ClassifierConfidence.high,
    )


def _save_input() -> NoteCreateRequest:
    return NoteCreateRequest(
        raw_text="raw",
        normalized_text="normalized",
        note_kind="note",
        source_ref=None,
        created_at="2024-01-01T00:00:00+00:00",
        tags=[],
    )


def _search_input() -> NoteSearchRequest:
    return NoteSearchRequest(
        query="mcp",
        time_range=None,
        tags=None,
        tag_match_mode=None,
        note_kinds=None,
        source_refs=None,
        limit=10,
        offset=0,
        sort=NoteSearchSort.created_at_desc,
    )


def _search_tags_input() -> TagSearchRequest:
    return TagSearchRequest(
        query="ai",
        time_range=None,
        note_kinds=None,
        source_refs=None,
        limit=10,
        offset=0,
        sort=TagSearchSort.usage_count_desc,
    )


def _update_input() -> UpdateExtractionResult:
    return UpdateExtractionResult(
        target_mode=UpdateTargetMode.latest_note,
        operations=[
            {
                "kind": NoteUpdateOperationKind.set_note_kind,
                "note_kind": "task",
            }
        ],
    )


@pytest.mark.asyncio
async def test_process_message_routes_save_note():
    service, classify, extract_save_input, _, _, save_graph, search_graph, search_tags_graph, update_graph = _service(
        classifier_result=_save_classification(),
        save_input=_save_input(),
        save_graph_state={
            "final_response": {
                "message": "Note saved.",
                "intent": BackendIntent.save_note.value,
                "result": {
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
            }
        },
    )

    response = await service.process_message(MessageRequest(text="чем отличаются prompts и resources"))

    assert response.intent == BackendIntent.save_note
    classify.assert_awaited_once_with("чем отличаются prompts и resources")
    extract_save_input.assert_awaited_once_with("чем отличаются prompts и resources")
    save_graph.ainvoke.assert_awaited_once()
    search_graph.ainvoke.assert_not_called()
    search_tags_graph.ainvoke.assert_not_called()
    update_graph.ainvoke.assert_not_called()
    graph_input = save_graph.ainvoke.await_args.args[0]
    assert graph_input["save_input"]["raw_text"] == "raw"
    assert graph_input["save_input"]["normalized_text"] == "normalized"


@pytest.mark.asyncio
async def test_process_message_routes_search_notes():
    service, classify, _, _, _, save_graph, search_graph, search_tags_graph, update_graph = _service(
        classifier_result=_search_classification(),
        search_input=_search_input(),
        search_graph_state={
            "final_response": {
                "message": "Found 1 notes.",
                "intent": BackendIntent.search_notes.value,
                "result": {
                    "notes": [
                        {
                            "id": "123e4567-e89b-12d3-a456-426614174001",
                            "raw_text": "mcp note",
                            "normalized_text": "mcp note",
                            "note_kind": "note",
                            "source_ref": None,
                            "created_at": "2024-01-01T00:00:00+00:00",
                            "updated_at": "2024-01-01T00:00:00+00:00",
                            "tags": [],
                        }
                    ]
                },
            }
        },
    )

    response = await service.process_message(MessageRequest(text="покажи мои заметки про mcp"))

    assert response.intent == BackendIntent.search_notes
    classify.assert_awaited_once_with("покажи мои заметки про mcp")
    search_graph.ainvoke.assert_awaited_once()
    save_graph.ainvoke.assert_not_called()
    search_tags_graph.ainvoke.assert_not_called()
    update_graph.ainvoke.assert_not_called()
    graph_input = search_graph.ainvoke.await_args.args[0]
    assert graph_input["search_input"]["query"] == "mcp"
    assert graph_input["search_input"]["sort"] == "created_at_desc"


@pytest.mark.asyncio
async def test_process_message_routes_search_tags():
    service, classify, _, extract_search_tags_input, _, save_graph, search_graph, search_tags_graph, update_graph = _service(
        classifier_result=_tags_classification(),
        search_tags_input=_search_tags_input(),
        search_tags_graph_state={
            "final_response": {
                "message": "Found 1 tags.",
                "intent": BackendIntent.search_tags.value,
                "result": {
                    "tags": [
                        {
                            "name": "ai",
                            "usage_count": 2,
                        }
                    ]
                },
            }
        },
    )

    response = await service.process_message(MessageRequest(text="какие у меня были темы по ai"))

    assert response.intent == BackendIntent.search_tags
    classify.assert_awaited_once_with("какие у меня были темы по ai")
    extract_search_tags_input.assert_awaited_once_with("какие у меня были темы по ai")
    search_tags_graph.ainvoke.assert_awaited_once()
    save_graph.ainvoke.assert_not_called()
    search_graph.ainvoke.assert_not_called()
    update_graph.ainvoke.assert_not_called()
    graph_input = search_tags_graph.ainvoke.await_args.args[0]
    assert graph_input["search_input"]["query"] == "ai"
    assert graph_input["search_input"]["sort"] == "usage_count_desc"


@pytest.mark.asyncio
async def test_process_message_routes_update_note():
    service, classify, _, _, extract_update_note_input, save_graph, search_graph, search_tags_graph, update_graph = _service(
        classifier_result=_update_classification(),
        update_input=_update_input(),
        update_graph_state={
            "final_response": {
                "message": "Note updated.",
                "intent": BackendIntent.update_note.value,
                "result": {
                    "note": {
                        "id": "123e4567-e89b-12d3-a456-426614174009",
                        "raw_text": "raw",
                        "normalized_text": "normalized",
                        "note_kind": "task",
                        "source_ref": None,
                        "created_at": "2024-01-01T00:00:00+00:00",
                        "updated_at": "2024-01-01T00:01:00+00:00",
                        "tags": [],
                    }
                },
            }
        },
    )

    response = await service.process_message(MessageRequest(text="исправь тип последней заметки на task"))

    assert response.intent == BackendIntent.update_note
    classify.assert_awaited_once_with("исправь тип последней заметки на task")
    extract_update_note_input.assert_awaited_once_with("исправь тип последней заметки на task")
    update_graph.ainvoke.assert_awaited_once()
    save_graph.ainvoke.assert_not_called()
    search_graph.ainvoke.assert_not_called()
    search_tags_graph.ainvoke.assert_not_called()
    graph_input = update_graph.ainvoke.await_args.args[0]
    assert graph_input["update_input"]["target_mode"] == "latest_note"


@pytest.mark.asyncio
async def test_process_message_preserves_intent_parse_error():
    service, *_ = _service(
        classifier_result=IntentParseError("bad input"),
    )

    with pytest.raises(IntentParseError):
        await service.process_message(MessageRequest(text="bad"))


@pytest.mark.asyncio
async def test_process_message_wraps_extractor_failure():
    service, *_ = _service(
        classifier_result=_save_classification(),
        save_input=RuntimeError("boom"),
    )

    with pytest.raises(BackendProcessingError):
        await service.process_message(MessageRequest(text="мысль"))
