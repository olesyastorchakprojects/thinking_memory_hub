from __future__ import annotations

from typing import Any

from langfuse import Langfuse

from backend.errors import (
    BackendProcessingError,
    InputExtractionError,
    IntentParseError,
    MemoryServerError,
    ModelClientError,
)
from backend.input_extractor import StructuredInputExtractor
from backend.intent_classifier import IntentClassifier
from backend.message_graph import build_message_graph
from backend.memory_client import MemoryClient
from backend.models import BackendIntent, MessageRequest, MessageResponse
from backend.search_notes_graph import build_search_notes_graph
from backend.search_tags_graph import build_search_tags_graph
from backend.update_note_graph import build_update_note_graph

_langfuse = Langfuse()


class MessageService:
    def __init__(
        self,
        *,
        memory_client: MemoryClient,
        intent_classifier: IntentClassifier,
        input_extractor: StructuredInputExtractor,
        save_graph: Any | None = None,
        search_notes_graph: Any | None = None,
        search_tags_graph: Any | None = None,
        update_note_graph: Any | None = None,
    ) -> None:
        self._intent_classifier = intent_classifier
        self._input_extractor = input_extractor
        self._save_graph = save_graph or build_message_graph(memory_client)
        self._search_notes_graph = search_notes_graph or build_search_notes_graph(memory_client)
        self._search_tags_graph = search_tags_graph or build_search_tags_graph(memory_client)
        self._update_note_graph = update_note_graph or build_update_note_graph(memory_client)

    async def process_message(self, request: MessageRequest) -> MessageResponse:
        trace = _langfuse.trace(name="process_message", input={"text": request.text})
        try:
            classification = await self._intent_classifier.classify(
                request.text, trace_id=trace.id
            )
            state = await self._invoke_graph(request.text, classification.intent, trace_id=trace.id)
            response = MessageResponse.model_validate(state["final_response"])
            trace.update(
                output={"intent": classification.intent.value, "message": response.message}
            )
            return response
        except (IntentParseError, MemoryServerError, BackendProcessingError):
            raise
        except (InputExtractionError, ModelClientError) as exc:
            raise BackendProcessingError("Failed to process message") from exc
        except Exception as exc:
            raise BackendProcessingError("Failed to process message") from exc

    async def _invoke_graph(
        self, user_message: str, intent: BackendIntent, *, trace_id: str
    ) -> dict:
        if intent == BackendIntent.save_note:
            save_input = await self._input_extractor.extract_save_input(
                user_message, trace_id=trace_id
            )
            return await self._save_graph.ainvoke(
                {"save_input": save_input.model_dump(mode="json")}
            )

        if intent == BackendIntent.search_notes:
            search_input = await self._input_extractor.extract_search_notes_input(
                user_message, trace_id=trace_id
            )
            return await self._search_notes_graph.ainvoke(
                {"search_input": search_input.model_dump(mode="json", by_alias=True)}
            )

        if intent == BackendIntent.search_tags:
            search_input = await self._input_extractor.extract_search_tags_input(
                user_message, trace_id=trace_id
            )
            return await self._search_tags_graph.ainvoke(
                {"search_input": search_input.model_dump(mode="json", by_alias=True)}
            )

        if intent == BackendIntent.update_note:
            update_input = await self._input_extractor.extract_update_note_input(
                user_message, trace_id=trace_id
            )
            return await self._update_note_graph.ainvoke(
                {"update_input": update_input.model_dump(mode="json")}
            )

        raise BackendProcessingError(f"Intent {intent.value!r} is not implemented yet")
