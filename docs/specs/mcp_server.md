# MCP Server

## 1. Purpose

This document defines the complete MCP server artifact for the thinking memory system.

This document is the source of truth for:

- `pyproject.toml`
- `app/memory_server/main.py`
- `app/memory_server/server.py`
- `app/memory_server/mcp_tools.py`
- `app/memory_server/models.py`
- `app/memory_server/storage_client.py`
- `app/memory_server/config.py`
- `app/memory_server/errors.py`
- `tests/test_mcp_tools.py`
- `tests/test_storage_client.py`
- `tests/test_models.py`
- `tests/test_config.py`
- `tests/integration/test_storage_client_integration.py`
- `tests/integration/test_mcp_server_integration.py`

This document uses:

- `docs/specs/data_contracts.md`
- `docs/specs/storage_client_interface.md`
- `docs/specs/mcp_tool_definitions.md`

## 2. Runtime Stack

The server must be implemented in Python.

The server must use:

- the official MCP Python SDK
- Pydantic
- psycopg
- psycopg_pool
- pytest

The server must expose MCP over Streamable HTTP.

The server implementation must use `FastMCP`.

## 3. File Tree

The server artifact must contain exactly this subtree:

```text
pyproject.toml
app/
  memory_server/
    __init__.py
    main.py
    server.py
    mcp_tools.py
    models.py
    storage_client.py
    config.py
    errors.py
tests/
  test_mcp_tools.py
  test_storage_client.py
  test_models.py
  test_config.py
  integration/
    test_storage_client_integration.py
    test_mcp_server_integration.py
```

## 4. Module Contracts

### 4.1 `app/memory_server/models.py`

This module must define Pydantic models for all server-used contracts from `docs/specs/data_contracts.md`.

This module must define exactly these public names:

- `NoteKind`
- `TagMatchMode`
- `NoteSearchSort`
- `TagSearchSort`
- `NoteUpdateOperationKind`
- `TimeRange`
- `NoteRecord`
- `NoteCreateRequest`
- `NoteSearchRequest`
- `TagSearchRequest`
- `SetNoteKindOperation`
- `SetNormalizedTextOperation`
- `ReplaceTagsOperation`
- `AddTagsOperation`
- `RemoveTagsOperation`
- `NoteUpdateOperation`
- `NoteUpdateRequest`
- `NoteList`
- `TagSearchResult`
- `TagList`

Rules:

- every public model must be derived directly from the corresponding contract in `docs/specs/data_contracts.md`
- `NoteUpdateOperation` must be a tagged union over:
  - `SetNoteKindOperation`
  - `SetNormalizedTextOperation`
  - `ReplaceTagsOperation`
  - `AddTagsOperation`
  - `RemoveTagsOperation`
- this module must not define storage logic
- this module must not define MCP tool handlers

### 4.2 `app/memory_server/errors.py`

This module must define exactly these public names:

- `SettingsError`
- `StorageClientError`
- `StorageNotFoundError`
- `StorageConflictError`
- `ToolInputValidationError`

Rules:

- `SettingsError` is raised only for configuration-loading failures
- `StorageClientError` is the parent error for storage-layer failures
- `StorageNotFoundError` is used when a requested note does not exist
- `StorageConflictError` is used when a storage write violates a uniqueness rule
- `ToolInputValidationError` is used when a JSON-compatible tool payload fails model validation

### 4.3 `app/memory_server/config.py`

This module must define exactly these public names:

- `Settings`
- `load_settings`

Required signatures:

```python
class Settings(BaseModel):
    memory_server_host: str
    memory_server_port: int
    database_url: str

def load_settings() -> Settings:
    ...
```

Rules:

- `load_settings()` must read environment variables
- `load_settings()` must return a validated `Settings` instance
- `load_settings()` must raise `SettingsError` on failure
- `Settings.memory_server_host` maps to `MEMORY_SERVER_HOST`
- `Settings.memory_server_port` maps to `MEMORY_SERVER_PORT`
- `Settings.database_url` maps to `DATABASE_URL`
- this module must not construct the MCP server
- this module must not create database connections

### 4.4 `app/memory_server/storage_client.py`

This module must define exactly these public names:

- `StorageClient`

Required signatures:

```python
class StorageClient:
    def __init__(self, database_url: str) -> None:
        ...

    async def open(self) -> None:
        ...

    async def close(self) -> None:
        ...

    async def create_note(self, request: NoteCreateRequest) -> NoteRecord:
        ...

    async def search_notes(self, request: NoteSearchRequest) -> NoteList:
        ...

    async def update_note(self, request: NoteUpdateRequest) -> NoteRecord:
        ...

    async def search_tags(self, request: TagSearchRequest) -> TagList:
        ...
```

Rules:

- this module must implement the interface defined in `docs/specs/storage_client_interface.md`
- this module owns PostgreSQL access
- this module owns SQL execution and transactions
- this module must use an async PostgreSQL connection pool
- `update_note` must apply all operations atomically
- storage-layer failures must raise `StorageClientError` or its child errors
- this module must not register MCP tools

### 4.5 `app/memory_server/mcp_tools.py`

This module must define exactly these public names:

- `handle_notes_save`
- `handle_notes_search`
- `handle_notes_update`
- `handle_tags_search`

Required signatures:

```python
async def handle_notes_save(arguments: dict, storage_client: StorageClient) -> dict:
    ...

async def handle_notes_search(arguments: dict, storage_client: StorageClient) -> dict:
    ...

async def handle_notes_update(arguments: dict, storage_client: StorageClient) -> dict:
    ...

async def handle_tags_search(arguments: dict, storage_client: StorageClient) -> dict:
    ...
```

Rules:

- each handler must accept one JSON-compatible argument object
- each handler must validate that argument object against the declared input contract
- each handler must construct the corresponding typed request object
- each handler must call exactly one bound storage-client method
- each handler must await the bound storage-client method
- each handler must serialize the typed result to one JSON-compatible result object
- input validation failure must raise `ToolInputValidationError`
- handlers must not contain SQL

Binding table:

| Handler | Input model | Storage method | Output model |
| --- | --- | --- | --- |
| `handle_notes_save` | `NoteCreateRequest` | `create_note` | `NoteRecord` |
| `handle_notes_search` | `NoteSearchRequest` | `search_notes` | `NoteList` |
| `handle_notes_update` | `NoteUpdateRequest` | `update_note` | `NoteRecord` |
| `handle_tags_search` | `TagSearchRequest` | `search_tags` | `TagList` |

### 4.6 `app/memory_server/server.py`

This module must define exactly these public names:

- `build_server`

Required signature:

```python
def build_server(storage_client: StorageClient) -> FastMCP:
    ...
```

Rules:

- `build_server` must create one `FastMCP` server object
- `build_server` must register exactly four tools:
  - `notes.save`
  - `notes.search`
  - `notes.update`
  - `tags.search`
- tool metadata must come from `docs/specs/mcp_tool_definitions.md`
- registered tool handlers must be:
  - `handle_notes_save`
  - `handle_notes_search`
  - `handle_notes_update`
  - `handle_tags_search`
- `build_server` must register FastMCP tools through async wrapper functions
- every wrapper function must accept FastMCP-typed arguments
- every wrapper function must use the most specific typed FastMCP parameter shape available from `app/memory_server/models.py`
- wrapper parameters must not degrade a declared typed contract to `dict`, `list[dict]`, or other less specific container types when a concrete model or tagged union already exists
- every wrapper function must construct one JSON-compatible argument object matching the internal handler contract
- every wrapper function must delegate to exactly one internal handler:
  - `handle_notes_save`
  - `handle_notes_search`
  - `handle_notes_update`
  - `handle_tags_search`
- the published FastMCP tool argument schema must be semantically equivalent to the corresponding `inputSchema` in `docs/specs/mcp_tool_definitions.md`
- item-level constraints from `docs/specs/mcp_tool_definitions.md` must be preserved in wrapper parameter typing
- nested object constraints from `docs/specs/mcp_tool_definitions.md` must be preserved in wrapper parameter typing
- internal handlers remain the source of truth for:
  - input validation
  - typed request construction
  - storage-client dispatch
  - result serialization
- this module must not load configuration
- this module must not open PostgreSQL connections by itself

### 4.7 `app/memory_server/main.py`

This module must define exactly these public names:

- `main`
- `run`

Required signature:

```python
async def run() -> None:
    ...

def main() -> None:
    ...
```

Startup sequence:

1. call `load_settings()`
2. construct `StorageClient(settings.database_url)`
3. await `storage_client.open()`
4. call `build_server(storage_client)`
5. start the MCP server over Streamable HTTP using:
   - `settings.memory_server_host`
   - `settings.memory_server_port`
6. ensure `await storage_client.close()` during shutdown

Rules:

- `run()` is the async startup entrypoint
- `main()` must call `asyncio.run(run())`
- this module must not define tool handlers
- this module must not define models

### 4.8 `pyproject.toml`

This file must define:

- project metadata
- Python version constraint
- runtime dependencies
- test dependencies
- console entrypoint for `main`
- pytest marker registration for `integration`

## 5. Tool Set

The server exposes exactly these tools:

- `notes.save`
- `notes.search`
- `notes.update`
- `tags.search`

## 6. Tool Invocation Contract

For every tool call:

1. the server receives one JSON-compatible argument object
2. the corresponding handler validates the argument object against the declared input contract
3. the handler constructs the typed request object
4. the handler calls the bound storage-client method
5. the storage-client method returns the typed response object
6. the handler serializes that typed response object to one JSON-compatible result object

When validation fails:

- the handler must raise `ToolInputValidationError`
- the storage client must not be called

## 7. Tool-to-Contract Bindings

| Tool | Input contract | Output contract | Storage method | Handler |
| --- | --- | --- | --- | --- |
| `notes.save` | `NoteCreateRequest` | `NoteRecord` | `create_note` | `handle_notes_save` |
| `notes.search` | `NoteSearchRequest` | `NoteList` | `search_notes` | `handle_notes_search` |
| `notes.update` | `NoteUpdateRequest` | `NoteRecord` | `update_note` | `handle_notes_update` |
| `tags.search` | `TagSearchRequest` | `TagList` | `search_tags` | `handle_tags_search` |

## 8. Configuration Contract

The server configuration consists of exactly these environment variables:

- `MEMORY_SERVER_HOST`
- `MEMORY_SERVER_PORT`
- `DATABASE_URL`
- `TEST_DATABASE_URL`

Rules:

- `MEMORY_SERVER_HOST` is required and must be a string
- `MEMORY_SERVER_PORT` is required and must be an integer
- `DATABASE_URL` is required and must be a PostgreSQL connection string
- `TEST_DATABASE_URL` is optional for normal application runtime
- `TEST_DATABASE_URL`, when set, must be a PostgreSQL connection string for the dedicated integration-test database

The repository-root `.env` file supplies local development values for these environment variables.

## 9. Error Model

### 9.1 Public error types

The server must define exactly these public error types:

- `SettingsError`
- `StorageClientError`
- `StorageNotFoundError`
- `StorageConflictError`
- `ToolInputValidationError`

### 9.2 Error hierarchy

- `StorageNotFoundError` must inherit from `StorageClientError`
- `StorageConflictError` must inherit from `StorageClientError`

### 9.3 Error behavior

- `load_settings()` must raise `SettingsError` when required environment variables are missing
- `load_settings()` must raise `SettingsError` when environment variable values have invalid types
- `load_settings()` must raise `SettingsError` when `DATABASE_URL` is not a PostgreSQL connection string
- `StorageClient.create_note()` must raise `StorageConflictError` when a uniqueness constraint is violated
- `StorageClient.update_note()` must raise `StorageNotFoundError` when `request.note_id` does not exist
- storage-layer failures not covered by a more specific storage error must raise `StorageClientError`
- every tool handler must raise `ToolInputValidationError` when the incoming JSON-compatible argument object does not satisfy the bound input contract
- when a tool handler raises `ToolInputValidationError`, the storage client must not be called

## 10. Unit Test Artifacts

The default unit test suite must run without access to a live PostgreSQL instance.

Rules:

- tests must use mocks, fakes, or stubs
- tests must not connect to a running PostgreSQL container
- tests must not require database provisioning
- MCP tool tests must use a mocked `StorageClient`
- `tests/test_storage_client.py` must be a unit-level contract test module for `StorageClient`

## 11. Integration Test Artifacts

Integration tests are a separate test layer from the unit test suite.

Rules:

- integration tests must live under `tests/integration/`
- integration tests are opt-in and must not be part of the default unit test run
- opt-in must be implemented with `pytest.mark.integration`
- `pyproject.toml` must register the `integration` marker
- the default unit test run must exclude tests marked `integration`
- integration tests must use `TEST_DATABASE_URL`
- `TEST_DATABASE_URL` must point to a dedicated integration-test PostgreSQL database
- when `TEST_DATABASE_URL` is unset, integration test setup must call `pytest.skip(...)`
- when `TEST_DATABASE_URL` is set but the database is unreachable, integration tests must fail
- integration tests may use a live local PostgreSQL database
- integration tests may use the local Docker PostgreSQL container
- integration tests must not mock the storage layer
- integration tests must use the schema from `db/schema.sql`
- integration tests must clean up their own test data
- integration tests must use isolated test records identified by unique `source_ref` values
- integration tests must remove their inserted test records during fixture teardown
- integration tests must not rely on transaction rollback as the primary isolation strategy
- integration tests must use a shared setup fixture or helper to apply `db/schema.sql` to the test database before test execution

### 11.1 `tests/integration/test_storage_client_integration.py`

This file must test:

- `StorageClient.open()` against a real PostgreSQL database
- `create_note()` writes rows to `notes`, `tags`, and `note_tags`
- `search_notes()` returns persisted notes and tags
- `search_notes()` query filtering works against `normalized_text`
- `update_note()` persists scalar and tag updates atomically
- `search_tags()` returns aggregated tag results derived from matching notes
- `source_ref` uniqueness raises `StorageConflictError`
- `update_note()` with a missing note raises `StorageNotFoundError`

### 11.2 `tests/integration/test_mcp_server_integration.py`

This file must test:

- `build_server()` creates a working `FastMCP` server instance
- registered tools are invocable through the in-process FastMCP runtime
- `notes.save` persists a note through the real storage layer
- `notes.search` returns persisted note data through the MCP tool boundary
- `notes.update` applies updates through the MCP tool boundary
- `tags.search` returns aggregated tag results through the MCP tool boundary
- published tool invocation succeeds with payloads satisfying `docs/specs/mcp_tool_definitions.md`

Rules:

- these tests must invoke tools in-process through the FastMCP runtime
- these tests must not use HTTP requests
- these tests must not start a separate network server process
- these tests must exercise the registered tool boundary rather than calling `handle_*` directly

## 12. Unit Test Artifacts

### 12.1 `tests/test_models.py`

This file must test:

- successful construction of every public request and response model
- rejection of invalid enum values
- rejection of invalid `TimeRange`
- tagged-union validation for `NoteUpdateOperation`

### 12.2 `tests/test_config.py`

This file must test:

- successful environment-based settings loading
- missing required environment variables
- invalid `MEMORY_SERVER_PORT`
- invalid `DATABASE_URL`

### 12.3 `tests/test_storage_client.py`

This file must test:

- `create_note`
- `search_notes`
- `update_note`
- `search_tags`
- atomicity of multi-operation `update_note`
- not-found behavior for `update_note`
- conflict behavior for `create_note`

This file must use mocked database boundaries.

This file must mirror the real psycopg async API used by `StorageClient`.

Rules:

- mocked database objects must reflect:
  - `AsyncConnectionPool.connection()`
  - `AsyncConnection.transaction()`
  - `AsyncConnection.cursor()`
  - cursor `execute()`
  - cursor `fetchone()`
  - cursor `fetchall()`
- tests must not rely on non-existent connection-level helpers such as `conn.fetch()` or `conn.fetchone()`

### 12.4 `tests/test_mcp_tools.py`

This file must test:

- successful invocation of each tool handler
- invalid payload rejection for each tool handler
- storage-client method dispatch for each tool handler
- serialization shape of each tool result
- absence of storage-client calls after tool input validation failure
- async invocation path of each tool handler

This file must use a mocked `StorageClient`.
