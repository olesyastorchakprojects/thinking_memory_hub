from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from backend.errors import IntentParseError
from backend.memory_client import MemoryClient
from backend.models import BackendIntent
from memory_server.models import TagSearchRequest


class SearchTagsGraphState(TypedDict, total=False):
    search_input: dict
    search_result: dict
    final_response: dict
    error: str


def build_search_tags_graph(memory_client: MemoryClient):
    async def validate_search_input(state: SearchTagsGraphState) -> SearchTagsGraphState:
        try:
            validated = TagSearchRequest.model_validate(state["search_input"])
        except Exception as exc:
            raise IntentParseError("search-tags input is invalid") from exc
        return {"search_input": validated.model_dump(mode="json", by_alias=True)}

    async def execute_search(state: SearchTagsGraphState) -> SearchTagsGraphState:
        search_result = await memory_client.tags_search(state["search_input"])
        return {"search_result": search_result}

    async def finalize_search_response(state: SearchTagsGraphState) -> SearchTagsGraphState:
        items = state["search_result"]["items"]
        return {
            "final_response": {
                "message": f"Found {len(items)} tags.",
                "intent": BackendIntent.search_tags.value,
                "result": {"tags": items},
            }
        }

    graph = StateGraph(SearchTagsGraphState)
    graph.add_node("validate_search_input", validate_search_input)
    graph.add_node("execute_search", execute_search)
    graph.add_node("finalize_search_response", finalize_search_response)
    graph.add_edge(START, "validate_search_input")
    graph.add_edge("validate_search_input", "execute_search")
    graph.add_edge("execute_search", "finalize_search_response")
    graph.add_edge("finalize_search_response", END)
    return graph.compile()
