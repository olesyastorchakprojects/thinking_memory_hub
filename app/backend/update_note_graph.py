from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from backend.errors import BackendProcessingError, IntentParseError
from backend.memory_client import MemoryClient
from backend.models import BackendIntent, UpdateExtractionResult, UpdateTargetMode
from memory_server.models import NoteSearchRequest, NoteSearchSort, NoteUpdateRequest


class UpdateNoteGraphState(TypedDict, total=False):
    update_input: dict
    resolved_note_id: str
    updated_note: dict
    final_response: dict
    error: str


def build_update_note_graph(memory_client: MemoryClient):
    async def validate_update_input(state: UpdateNoteGraphState) -> UpdateNoteGraphState:
        try:
            validated = UpdateExtractionResult.model_validate(state["update_input"])
        except Exception as exc:
            raise IntentParseError("update input is invalid") from exc
        return {"update_input": validated.model_dump(mode="json")}

    async def resolve_target_note_id(state: UpdateNoteGraphState) -> UpdateNoteGraphState:
        update_input = UpdateExtractionResult.model_validate(state["update_input"])

        if update_input.target_mode == UpdateTargetMode.latest_note:
            latest_note_request = NoteSearchRequest(
                query=None,
                time_range=None,
                tags=None,
                tag_match_mode=None,
                note_kinds=None,
                source_refs=None,
                limit=1,
                offset=0,
                sort=NoteSearchSort.created_at_desc,
            )
            result = await memory_client.notes_search(
                latest_note_request.model_dump(mode="json", by_alias=True)
            )
            items = result.get("items", [])
            if not items:
                raise BackendProcessingError("No notes are available to update")
            return {"resolved_note_id": items[0]["id"]}

        raise BackendProcessingError("Update target could not be resolved")

    async def execute_update(state: UpdateNoteGraphState) -> UpdateNoteGraphState:
        request = NoteUpdateRequest(
            note_id=state["resolved_note_id"],
            operations=state["update_input"]["operations"],
        )
        updated_note = await memory_client.notes_update(request.model_dump(mode="json"))
        return {"updated_note": updated_note}

    async def finalize_update_response(state: UpdateNoteGraphState) -> UpdateNoteGraphState:
        return {
            "final_response": {
                "message": "Note updated.",
                "intent": BackendIntent.update_note.value,
                "result": {"note": state["updated_note"]},
            }
        }

    graph = StateGraph(UpdateNoteGraphState)
    graph.add_node("validate_update_input", validate_update_input)
    graph.add_node("resolve_target_note_id", resolve_target_note_id)
    graph.add_node("execute_update", execute_update)
    graph.add_node("finalize_update_response", finalize_update_response)
    graph.add_edge(START, "validate_update_input")
    graph.add_edge("validate_update_input", "resolve_target_note_id")
    graph.add_edge("resolve_target_note_id", "execute_update")
    graph.add_edge("execute_update", "finalize_update_response")
    graph.add_edge("finalize_update_response", END)
    return graph.compile()
