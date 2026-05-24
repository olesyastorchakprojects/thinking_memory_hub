from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from backend.errors import IntentParseError
from backend.memory_client import MemoryClient
from backend.models import BackendIntent
from memory_server.models import NoteCreateRequest


class MessageGraphState(TypedDict, total=False):
    save_input: dict
    saved_note: dict
    final_response: dict
    error: str


def build_message_graph(memory_client: MemoryClient):
    async def validate_save_input(state: MessageGraphState) -> MessageGraphState:
        try:
            validated = NoteCreateRequest.model_validate(state["save_input"])
        except Exception as exc:
            raise IntentParseError("save input is invalid") from exc
        return {"save_input": validated.model_dump(mode="json")}

    async def execute_save(state: MessageGraphState) -> MessageGraphState:
        saved_note = await memory_client.notes_save(state["save_input"])
        return {"saved_note": saved_note}

    async def finalize_save_response(state: MessageGraphState) -> MessageGraphState:
        return {
            "final_response": {
                "message": "Note saved.",
                "intent": BackendIntent.save_note.value,
                "result": {"note": state["saved_note"]},
            }
        }

    graph = StateGraph(MessageGraphState)
    graph.add_node("validate_save_input", validate_save_input)
    graph.add_node("execute_save", execute_save)
    graph.add_node("finalize_save_response", finalize_save_response)
    graph.add_edge(START, "validate_save_input")
    graph.add_edge("validate_save_input", "execute_save")
    graph.add_edge("execute_save", "finalize_save_response")
    graph.add_edge("finalize_save_response", END)
    return graph.compile()
