# Backend Server

## 1. Purpose

This document defines the complete backend server artifact for the thinking
memory system.

This document is the source of truth for:

- `pyproject.toml`
- `app/backend/__init__.py`
- `app/backend/main.py`
- `app/backend/server.py`
- `app/backend/api.py`
- `app/backend/models.py`
- `app/backend/config.py`
- `app/backend/errors.py`
- `app/backend/message_graph.py`
- `app/backend/message_service.py`
- `app/backend/memory_client.py`
- `tests/test_backend_api.py`
- `tests/test_backend_models.py`
- `tests/test_backend_config.py`
- `tests/test_message_graph.py`
- `tests/test_message_service.py`
- `tests/test_memory_client.py`
- `tests/integration/test_backend_api_integration.py`
- `tests/integration/test_backend_memory_integration.py`

This document uses:

- `docs/specs/backend_api.md`
- `docs/specs/data_contracts.md`
- `docs/specs/mcp_tool_definitions.md`
- `docs/specs/backend_save_graph.md`
- `docs/specs/backend_search_notes_graph.md`

## 2. Runtime Stack

The backend must be implemented in Python.

The backend must use:

- FastAPI
- Pydantic
- LangGraph
- the official MCP Python SDK
- httpx
- pytest

The backend must expose HTTP REST endpoints.

The backend must call the remote memory server through MCP.

## 3. File Tree

The backend artifact must contain exactly this subtree:

```text
pyproject.toml
app/
  backend/
    __init__.py
    main.py
    server.py
    api.py
    models.py
    config.py
    errors.py
    message_graph.py
    message_service.py
    memory_client.py
tests/
  test_backend_api.py
  test_backend_models.py
  test_backend_config.py
  test_message_graph.py
  test_message_service.py
  test_memory_client.py
  integration/
    test_backend_api_integration.py
    test_backend_memory_integration.py
```

## 4. Module Contracts

### 4.1 `app/backend/models.py`

This module must define Pydantic models for all backend-used contracts from
`docs/specs/backend_api.md`.

This module must define exactly these public names:

- `BackendIntent`
- `BackendErrorCode`
- `HealthResponse`
- `MessageRequest`
- `SaveNoteResult`
- `SearchNotesResult`
- `SearchTagsResult`
- `UpdateNoteResult`
- `MessageResult`
- `MessageResponse`
- `ErrorBody`
- `ErrorResponse`

Rules:

- every public model must be derived directly from the corresponding contract in
  `docs/specs/backend_api.md`
- `MessageResult` must be a tagged union over:
  - `SaveNoteResult`
  - `SearchNotesResult`
  - `SearchTagsResult`
  - `UpdateNoteResult`
- this module must not define FastAPI routes
- this module must not define LangGraph nodes

### 4.2 `app/backend/errors.py`

This module must define exactly these public names:

- `BackendSettingsError`
- `IntentParseError`
- `BackendProcessingError`
- `MemoryServerError`

Rules:

- `BackendSettingsError` is raised only for configuration-loading failures
- `IntentParseError` is raised only when the backend cannot determine one valid
  `BackendIntent`
- `BackendProcessingError` is raised only for backend orchestration failures
- `MemoryServerError` is raised only when the remote MCP memory server call
  fails or returns an invalid result

### 4.3 `app/backend/config.py`

This module must define exactly these public names:

- `BackendSettings`
- `load_settings`

Required signatures:

```python
class BackendSettings(BaseModel):
    backend_host: str
    backend_port: int
    memory_server_url: str

def load_settings() -> BackendSettings:
    ...
```

Rules:

- `load_settings()` must read environment variables
- `load_settings()` must return a validated `BackendSettings` instance
- `load_settings()` must raise `BackendSettingsError` on failure
- `BackendSettings.backend_host` maps to `BACKEND_HOST`
- `BackendSettings.backend_port` maps to `BACKEND_PORT`
- `BackendSettings.memory_server_url` maps to `MEMORY_SERVER_URL`
- this module must not construct FastAPI
- this module must not call the remote memory server

### 4.4 `app/backend/memory_client.py`

This module must define exactly these public names:

- `MemoryClient`

Required signatures:

```python
class MemoryClient:
    def __init__(self, memory_server_url: str) -> None:
        ...

    async def open(self) -> None:
        ...

    async def close(self) -> None:
        ...

    async def notes_save(self, request: dict) -> dict:
        ...

    async def notes_search(self, request: dict) -> dict:
        ...

    async def notes_update(self, request: dict) -> dict:
        ...

    async def tags_search(self, request: dict) -> dict:
        ...
```

Rules:

- this module owns outbound MCP communication to the remote memory server
- this module must use the official MCP Python SDK client runtime
- this module must open and close its own MCP client resources
- this module must send JSON-compatible arguments matching
  `docs/specs/mcp_tool_definitions.md`
- this module must return JSON-compatible results matching
  `docs/specs/mcp_tool_definitions.md`
- remote call failures must raise `MemoryServerError`
- this module must not contain FastAPI routing
- this module must not contain LangGraph routing logic

### 4.5 `app/backend/message_graph.py`

This module must define exactly these public names:

- `MessageGraphState`
- `build_message_graph`

Required signatures:

```python
class MessageGraphState(TypedDict, total=False):
    save_input: dict
    saved_note: dict
    final_response: dict
    error: str

def build_message_graph(memory_client: MemoryClient):
    ...
```

Rules:

- this module owns LangGraph construction
- the current implementation target is the `save_note` graph
- the graph must accept one typed save request, not raw user text
- the graph must contain exactly these conceptual stages:
  - validate typed save input
  - invoke one memory-server tool
  - build final backend response
- this module must not expose FastAPI routes

### 4.6 `app/backend/message_service.py`

This module must define exactly these public names:

- `MessageService`

Required signatures:

```python
class MessageService:
    def __init__(self, memory_client: MemoryClient) -> None:
        ...

    async def process_message(self, request: MessageRequest) -> MessageResponse:
        ...
```

Rules:

- this module owns orchestration between request validation, LangGraph
  execution, and response construction
- `process_message()` must execute the LangGraph built by
  `build_message_graph()`
- `process_message()` must return a validated `MessageResponse`
- `process_message()` must not call PostgreSQL directly

### 4.7 `app/backend/api.py`

This module must define exactly these public names:

- `create_api_router`

Required signature:

```python
def create_api_router(message_service: MessageService):
    ...
```

Rules:

- this module owns FastAPI route registration for:
  - `GET /api/health`
  - `POST /api/message`
- `GET /api/health` must return `HealthResponse`
- `POST /api/message` must accept `MessageRequest`
- `POST /api/message` must return `MessageResponse` on success
- `POST /api/message` must return `ErrorResponse` on failure
- this module must not contain MCP client code

### 4.8 `app/backend/server.py`

This module must define exactly these public names:

- `build_app`

Required signature:

```python
def build_app(message_service: MessageService):
    ...
```

Rules:

- this module must construct the FastAPI application
- this module must include the router created by `create_api_router()`
- this module must not construct `BackendSettings`
- this module must not contain LangGraph node logic

### 4.9 `app/backend/main.py`

This module must define exactly these public names:

- `run`
- `main`

Required signatures:

```python
async def run() -> None:
    ...

def main() -> None:
    ...
```

Rules:

- `run()` must:
  - load settings
  - construct `MemoryClient`
  - open `MemoryClient`
  - construct `MessageService`
  - construct FastAPI via `build_app()`
  - start the HTTP server
  - close `MemoryClient` in `finally`
- `main()` must be the synchronous entrypoint that runs `run()`

## 5. REST Boundary Contract

The backend must publish exactly these endpoints:

- `GET /api/health`
- `POST /api/message`

The backend must not publish any additional public routes in `v1`.

The backend must serialize and validate payloads according to
`docs/specs/backend_api.md`.

## 6. LangGraph Boundary Contract

LangGraph is required only inside the backend.

LangGraph responsibilities:

- determine one backend intent from the user message
- build one JSON-compatible request for the remote memory server
- invoke exactly one MCP tool in the selected execution path
- build one final backend response object

LangGraph must not:

- access PostgreSQL directly
- import SQL
- register MCP tools
- expose HTTP routes

## 7. MCP Client Boundary Contract

The backend must treat the memory server as a remote MCP dependency.

The backend must invoke only these remote tools:

- `notes.save`
- `notes.search`
- `notes.update`
- `tags.search`

The backend must not call the storage layer directly.

## 8. Config Contract

The backend must read configuration from environment variables.

Required environment variables:

- `BACKEND_HOST`
- `BACKEND_PORT`
- `MEMORY_SERVER_URL`

If any required environment variable is missing or invalid,
`load_settings()` must raise `BackendSettingsError`.

## 9. Error Mapping Contract

### 9.1 Invalid Request

- invalid `MessageRequest` input must map to `ErrorResponse`
- `error.code` must be `invalid_request`

### 9.2 Intent Parsing Failure

- failure to determine one valid backend intent must map to `ErrorResponse`
- `error.code` must be `intent_parse_failed`

### 9.3 Backend Processing Failure

- internal orchestration failures must map to `ErrorResponse`
- `error.code` must be `backend_processing_failed`

### 9.4 Memory Server Failure

- remote MCP failures must map to `ErrorResponse`
- `error.code` must be `memory_server_error`

## 10. Unit Test Contract

### 10.1 Required Unit Test Files

The backend artifact must include exactly these unit test files:

- `tests/test_backend_api.py`
- `tests/test_backend_models.py`
- `tests/test_backend_config.py`
- `tests/test_message_graph.py`
- `tests/test_message_service.py`
- `tests/test_memory_client.py`

### 10.2 Unit Test Rules

Unit tests must not:

- start a real HTTP server
- call the live remote MCP server
- call PostgreSQL

Unit tests must use mocks or fakes for:

- `MemoryClient`
- LangGraph execution boundary
- outbound MCP client boundary

### 10.3 Required Unit Test Coverage

`tests/test_backend_models.py` must verify:

- model validation for all backend API models
- tagged-union behavior for `MessageResult`

`tests/test_backend_config.py` must verify:

- successful loading from env
- missing env failure
- invalid env failure

`tests/test_memory_client.py` must verify:

- correct remote tool name dispatch
- correct JSON-compatible request payloads
- correct JSON-compatible response handling
- remote failure mapping to `MemoryServerError`

`tests/test_message_graph.py` must verify:

- intent routing for all four supported intents
- one-tool dispatch in each execution path
- error path for unsupported or unparseable input

`tests/test_message_service.py` must verify:

- successful `MessageResponse` construction for each intent
- mapping of graph failures to backend errors

`tests/test_backend_api.py` must verify:

- `GET /api/health` returns `HealthResponse`
- `POST /api/message` accepts `MessageRequest`
- `POST /api/message` returns `MessageResponse` on success
- `POST /api/message` returns `ErrorResponse` on failure

## 11. Integration Test Contract

### 11.1 Required Integration Test Files

The backend artifact must include exactly these integration test files:

- `tests/integration/test_backend_api_integration.py`
- `tests/integration/test_backend_memory_integration.py`

### 11.2 Integration Test Rules

Integration tests:

- must be marked with `pytest.mark.integration`
- must not be part of the default unit test run
- may use a live local backend process or in-process FastAPI app
- may use a live local MCP memory server
- must not call PostgreSQL directly

Integration tests must read the remote memory-server endpoint from:

- `MEMORY_SERVER_URL`

If `MEMORY_SERVER_URL` is not set for the integration environment, the tests
must call `pytest.skip(...)`.

If `MEMORY_SERVER_URL` is set but unreachable, the integration tests must fail.

### 11.3 Required Integration Test Coverage

`tests/integration/test_backend_memory_integration.py` must verify:

- backend memory client can call `notes.save`
- backend memory client can call `notes.search`
- backend memory client can call `notes.update`
- backend memory client can call `tags.search`

`tests/integration/test_backend_api_integration.py` must verify:

- `GET /api/health` through the FastAPI runtime
- `POST /api/message` end-to-end for:
  - one save flow
  - one note search flow
  - one tag search flow
  - one update flow
- returned HTTP payload matches `docs/specs/backend_api.md`
