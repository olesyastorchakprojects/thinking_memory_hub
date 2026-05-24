# Backend Search Notes Graph

## 1. Purpose

This document defines the `search_notes` graph used by the backend.

This document defines:

- the graph state shape
- the graph node names
- the node input and output contracts
- the execution order

This document defines only the `search_notes` graph.

## 2. Scope

The graph defined by this document is the minimal backend orchestration flow for
executing one typed note search request through the remote MCP memory server.

The graph defined by this document:

- accepts one typed search request
- invokes the remote memory server once
- returns one backend `MessageResponse`

The graph defined by this document does not:

- parse raw user text
- classify intent
- generate search fields from natural language
- route to any other intent

## 3. State Contract

### 3.1 `SearchNotesGraphState`

Canonical shape:

```python
class SearchNotesGraphState(TypedDict, total=False):
    search_input: dict
    search_result: dict
    final_response: dict
    error: str
```

State field semantics:

- `search_input`
  - one JSON-compatible request object for remote tool `notes.search`
- `search_result`
  - one JSON-compatible search result object returned by the memory server
- `final_response`
  - one JSON-compatible backend response object
- `error`
  - one human-readable error string

### 3.2 `total=False`

`total=False` means the state is partial.

This means:

- not every key is required at graph start
- each node may add fields progressively
- a node may read only the fields that are guaranteed by preceding nodes

The initial graph input contains only:

```yaml
search_input: dict
```

The expected terminal graph output contains:

```yaml
final_response: dict
```

## 4. Node Contracts

### 4.1 `validate_search_input`

#### Input fields

- `search_input`

#### Output fields

- no new state field is required

#### Responsibilities

This node must:

- validate `search_input` against the `NoteSearchRequest` contract from
  `docs/specs/data_contracts.md`
- preserve the validated payload as the request object used by
  `execute_search`

#### Error rules

If `search_input` does not satisfy `NoteSearchRequest`, the node must fail.

### 4.2 `execute_search`

#### Input fields

- `search_input`

#### Output fields

- `search_result`

#### Responsibilities

This node must:

- call `memory_client.notes_search(search_input)`
- store the returned JSON-compatible search object as `search_result`

#### Error rules

If the remote call fails, the node must fail.

### 4.3 `finalize_search_response`

#### Input fields

- `search_result`

#### Output fields

- `final_response`

#### Responsibilities

This node must construct one backend success response.

#### Output shape

The node must produce:

```yaml
message: string
intent: string
result:
  notes: list[dict]
```

#### Required construction rules

- `message = "Found N notes."`
- `intent = "search_notes"`
- `N = len(search_result["items"])`
- `result.notes = search_result["items"]`

The final response must match `MessageResponse` from
`docs/specs/backend_api.md`.

## 5. Graph Topology

The graph must contain exactly these nodes:

- `validate_search_input`
- `execute_search`
- `finalize_search_response`

The graph must contain exactly this execution order:

- `START -> validate_search_input`
- `validate_search_input -> execute_search`
- `execute_search -> finalize_search_response`
- `finalize_search_response -> END`

No additional branch nodes are defined by this document.

## 6. Integration Boundaries

### 6.1 Backend Boundary

The graph input is one typed backend search request.

The graph output is one backend `MessageResponse`.

### 6.2 Memory Server Boundary

The graph must invoke exactly one remote tool:

- `notes.search`

The graph must not call:

- `notes.save`
- `notes.update`
- `tags.search`

### 6.3 LangGraph Boundary

The graph state is a shared state object passed between nodes.

Each node:

- receives the current state
- reads the fields it needs
- returns a partial state update

The graph runtime merges node outputs into the shared state as execution
continues.

## 7. Test Contract

### 7.1 Unit Tests

Unit tests for this graph must verify:

- `validate_search_input` accepts a valid `NoteSearchRequest` payload
- `validate_search_input` rejects an invalid `NoteSearchRequest` payload
- `execute_search` calls `memory_client.notes_search()` exactly once
- `finalize_search_response` returns `intent = "search_notes"`
- the full graph produces one valid `MessageResponse`

### 7.2 Integration Tests

Integration tests for this graph must verify:

- one backend search-notes flow reaches the remote memory server
- the remote memory server returns a note list
- the backend returns `intent = "search_notes"`
- the backend returns `result.notes`
