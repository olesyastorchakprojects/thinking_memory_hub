# Backend Save Graph

## 1. Purpose

This document defines the `save_note` graph used by the backend.

This document defines:

- the graph state shape
- the graph node names
- the node input and output contracts
- the execution order

This document defines only the `save_note` graph.

## 2. Scope

The graph defined by this document is the minimal backend orchestration flow for
saving one typed note request through the remote MCP memory server.

The graph defined by this document:

- accepts one typed save request
- invokes the remote memory server once
- returns one backend `MessageResponse`

The graph defined by this document does not:

- parse raw user text
- classify intent
- generate note fields from natural language
- route to any other intent

## 3. State Contract

### 3.1 `SaveGraphState`

Canonical shape:

```python
class SaveGraphState(TypedDict, total=False):
    save_input: dict
    saved_note: dict
    final_response: dict
    error: str
```

State field semantics:

- `save_input`
  - one JSON-compatible request object for remote tool `notes.save`
- `saved_note`
  - one JSON-compatible note object returned by the memory server
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
save_input: dict
```

The expected terminal graph output contains:

```yaml
final_response: dict
```

## 4. Node Contracts

### 4.1 `validate_save_input`

#### Input fields

- `save_input`

#### Output fields

- no new state field is required

#### Responsibilities

This node must:

- validate `save_input` against the `NoteCreateRequest` contract from
  `docs/specs/data_contracts.md`
- preserve the validated payload as the request object used by `execute_save`

#### Error rules

If `save_input` does not satisfy `NoteCreateRequest`, the node must fail.

### 4.2 `execute_save`

#### Input fields

- `save_input`

#### Output fields

- `saved_note`

#### Responsibilities

This node must:

- call `memory_client.notes_save(save_input)`
- store the returned JSON-compatible note object as `saved_note`

#### Error rules

If the remote call fails, the node must fail.

### 4.3 `finalize_save_response`

#### Input fields

- `saved_note`

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
  note: dict
```

#### Required construction rules

- `message = "Note saved."`
- `intent = "save_note"`
- `result.note = saved_note`

The final response must match `MessageResponse` from
`docs/specs/backend_api.md`.

## 5. Graph Topology

The graph must contain exactly these nodes:

- `validate_save_input`
- `execute_save`
- `finalize_save_response`

The graph must contain exactly this execution order:

- `START -> validate_save_input`
- `validate_save_input -> execute_save`
- `execute_save -> finalize_save_response`
- `finalize_save_response -> END`

No additional branch nodes are defined by this document.

## 6. Integration Boundaries

### 6.1 Backend Boundary

The graph input is one typed backend save request.

The graph output is one backend `MessageResponse`.

### 6.2 Memory Server Boundary

The graph must invoke exactly one remote tool:

- `notes.save`

The graph must not call:

- `notes.search`
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

- `validate_save_input` accepts a valid `NoteCreateRequest` payload
- `validate_save_input` rejects an invalid `NoteCreateRequest` payload
- `execute_save` calls `memory_client.notes_save()` exactly once
- `finalize_save_response` returns `intent = "save_note"`
- the full graph produces one valid `MessageResponse`

### 7.2 Integration Tests

Integration tests for this graph must verify:

- one backend save flow reaches the remote memory server
- the remote memory server returns a persisted note
- the backend returns `message = "Note saved."`
- the backend returns `intent = "save_note"`
