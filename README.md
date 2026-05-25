# Thinking Memory Hub

Thinking Memory Hub is a Python memory system built around three core ideas:

- MCP as the stable tool boundary for memory operations
- LangGraph as the orchestration layer for user-facing workflows
- Langfuse as the observability layer for LLM-powered orchestration

At the storage boundary, the project exposes a PostgreSQL-backed MCP server. At the application boundary, it uses LangGraph-driven backend flows to classify user intent, build typed requests, call MCP tools, and return user-facing responses.

The project is designed for messenger integrations. Slack is the first implemented channel, and the backend architecture allows the same MCP and LangGraph core to support additional messengers.

The storage server currently publishes four MCP tools:

- `notes.save`
- `notes.search`
- `notes.update`
- `tags.search`

The repository also contains a backend HTTP API that accepts natural-language requests and routes them through LangGraph workflows backed by the remote MCP memory server.

## Architecture

The core boundary in this project is:

```text
app/backend code -> MCP memory server -> Postgres
```

The higher-level runtime flow is:

```text
user message
  -> backend API
  -> intent classification
  -> structured input extraction
  -> LangGraph workflow
  -> remote MCP tool call
  -> PostgreSQL storage/query
```

Langfuse instrumentation spans the backend orchestration and LLM calls within that flow.

Responsibilities:

- `app/memory_server/` owns MCP transport, tool registration, request validation, and storage calls
- `app/memory_server/storage_client.py` owns SQL, transactions, and PostgreSQL access
- `app/backend/` owns the REST API, intent routing, LangGraph orchestration, and remote MCP calls
- `Langfuse` owns observability for backend traces and LLM generations

## Current Scope

The normative implementation scope is defined in `docs/specs/`.

Current scope includes:

- an MCP memory server exposed over Streamable HTTP via `FastMCP`
- a LangGraph-backed backend that orchestrates natural-language memory workflows
- Langfuse-backed observability for backend request traces and model calls
- a Slack integration that turns the backend into a conversational assistant inside a messenger
- PostgreSQL-backed note persistence with tags
- a backend REST API with `GET /api/health`
- a backend REST API with `POST /api/message`
- a Slack Events API endpoint, enabled when Slack credentials are configured

## Tech Stack

- Python 3.11+
- FastMCP / MCP Python SDK
- FastAPI
- LangGraph
- Pydantic
- psycopg + psycopg_pool
- PostgreSQL
- Langfuse

## Repository Layout

```text
app/
  backend/
  memory_server/
db/
  schema.sql
docs/
  index.md
  specs/
tests/
  integration/
```

Key entrypoints:

- `app/memory_server/main.py`
- `app/memory_server/server.py`
- `app/memory_server/mcp_tools.py`
- `app/memory_server/storage_client.py`
- `app/backend/main.py`
- `app/backend/message_service.py`
- `app/backend/message_graph.py`
- `app/backend/search_notes_graph.py`
- `app/backend/search_tags_graph.py`
- `app/backend/update_note_graph.py`

## Source of Truth

When working on the project, treat `docs/specs/` as normative.

Recommended reading order:

1. `docs/index.md`
2. `docs/specs/mcp_server.md`
3. `docs/specs/data_contracts.md`
4. `docs/specs/mcp_tool_definitions.md`
5. `docs/specs/storage_client_interface.md`

Backend-specific contracts are documented in:

- `docs/specs/backend_api.md`
- `docs/specs/backend_server.md`
- `docs/specs/backend_save_graph.md`
- `docs/specs/backend_search_notes_graph.md`

## Why MCP + LangGraph

This project was written around the combination of MCP and LangGraph, not just as a CRUD note service.

MCP gives the system a clean tool contract:

- the memory server publishes a small, typed, stable tool surface
- backend and external clients can call memory operations without knowing SQL or schema details
- storage concerns stay behind the MCP boundary

LangGraph gives the system a clean orchestration model:

- each user intent is executed as an explicit graph instead of ad-hoc controller logic
- graph nodes validate inputs, call MCP tools, and assemble final responses step by step
- workflows can evolve from simple single-tool executions into richer multi-step reasoning flows

In this architecture:

- PostgreSQL is the persistence engine
- MCP is the application protocol between orchestration and storage capabilities
- LangGraph is the place where higher-level behavior lives
- Langfuse is where LLM workflow execution becomes traceable and inspectable
- messenger adapters are the user-facing entrypoints that can sit on top of the same orchestration core

## LangGraph Workflows

The backend defines a separate graph per intent:

- `save_note`
- `search_notes`
- `search_tags`
- `update_note`

These graphs are assembled in [`app/backend/message_service.py`](app/backend/message_service.py), which:

- classifies the incoming message intent
- extracts typed structured input for that intent
- invokes the matching LangGraph workflow
- validates the final backend response

Current graph implementations live in:

- [`app/backend/message_graph.py`](app/backend/message_graph.py)
- [`app/backend/search_notes_graph.py`](app/backend/search_notes_graph.py)
- [`app/backend/search_tags_graph.py`](app/backend/search_tags_graph.py)
- [`app/backend/update_note_graph.py`](app/backend/update_note_graph.py)

Typical graph shape for save/search flows:

```text
validate typed input
  -> execute one MCP tool call
  -> build final response
```

The update flow is already a bit richer:

```text
validate update input
  -> resolve target note
  -> execute MCP update
  -> build final response
```

This layer can be extended as more memory workflows are added.

## Messenger Integrations

The system is designed to work as a memory assistant inside messengers, not only as a standalone API.

The current project includes one messenger integration:

- Slack

The architecture supports additional channels because the layers are already separated:

- messenger adapter receives a user message
- backend turns it into structured intent-driven workflow execution
- LangGraph orchestrates the flow
- MCP provides the stable memory tool boundary
- the storage server stays unchanged regardless of which messenger sent the request

This separation keeps messenger-specific concerns, such as webhook verification or reply formatting, out of the memory server itself.

## Slack Integration

Slack is the first implemented messenger integration in the current project scope.

![Slack integration demo](docs/images/slack.png)

Capabilities:

- receives Slack Events API requests on `/slack/events`
- verifies Slack signatures before processing events
- handles Slack `url_verification`
- processes `app_mention` events
- strips the bot mention and forwards the remaining user text into `MessageService`
- posts the backend response back to Slack, typically in the same thread context
- deduplicates repeated Slack event deliveries in memory

Operational characteristics:

- users can interact with the memory system from a real conversation surface
- the same LangGraph workflows used by the HTTP API are reused from Slack
- the messenger UX stays thin while the real logic remains in MCP, LangGraph, and the backend service layer

Current limitations:

- Slack is the only implemented messenger right now
- the current Slack flow is centered on `app_mention`
- direct messages are not wired yet

Slack-specific implementation lives in:

- [`app/backend/slack.py`](app/backend/slack.py)
- [`docs/slack_setup.md`](docs/slack_setup.md)

## Observability With Langfuse

Langfuse is part of the backend design.

The current implementation uses it to observe the orchestration pipeline around LangGraph and LLM calls:

- [`app/backend/message_service.py`](app/backend/message_service.py) creates a top-level `process_message` trace
- that `trace_id` is propagated into intent classification and structured input extraction
- [`app/backend/model_client.py`](app/backend/model_client.py) records generation spans for model calls
- model spans capture request input, output, token usage, and calculated input/output cost

This gives the project visibility into:

- which user message triggered which workflow
- which intent was selected
- which extractor/classifier/model span ran under the same trace
- how much token usage and estimated cost each LLM step produced

Summary:

- LangGraph defines the workflow
- MCP defines the tool boundary
- Langfuse lets you inspect what happened while that workflow was running

## MCP Surface

The MCP server is intentionally small and typed. Each tool handler validates input, calls exactly one storage method, and serializes a typed result.

Published tools:

- `notes.save`
- `notes.search`
- `notes.update`
- `tags.search`

The server implementation is centered in:

- [`app/memory_server/server.py`](app/memory_server/server.py)
- [`app/memory_server/mcp_tools.py`](app/memory_server/mcp_tools.py)
- [`app/memory_server/storage_client.py`](app/memory_server/storage_client.py)

## Data Model

Notes are stored as structured records with:

- `id`
- `raw_text`
- `normalized_text`
- `note_kind`
- `source_ref`
- `created_at`
- `updated_at`
- `tags`

Supported `note_kind` values:

- `note`
- `question`
- `task`
- `reading`
- `watch`

Tag search returns aggregated tag results with usage counts derived from matching notes.

## Database

Schema lives in [`db/schema.sql`](db/schema.sql).

The schema creates:

- `notes`
- `tags`
- `note_tags`

It also enables required PostgreSQL extensions:

- `pgcrypto`
- `pg_trgm`

`pg_trgm` is used for similarity search in note and tag queries.

## Setup

### 1. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

### 2. Create a PostgreSQL database

Create a database and apply the schema:

```bash
psql "$DATABASE_URL" -f db/schema.sql
```

### 3. Configure environment variables

For the MCP memory server:

```bash
export MEMORY_SERVER_HOST=127.0.0.1
export MEMORY_SERVER_PORT=8001
export DATABASE_URL=postgresql://user:pass@localhost:5432/thinking_memory_hub
```

For the backend API:

```bash
export BACKEND_HOST=127.0.0.1
export BACKEND_PORT=8081
export MEMORY_SERVER_URL=http://127.0.0.1:8001/mcp
export TOGETHER_URL=https://api.together.xyz
export TOGETHER_API_KEY=your_api_key
export TOGETHER_MODEL=openai/gpt-oss-20b
```

Optional Slack variables:

```bash
export SLACK_SIGNING_SECRET=...
export SLACK_BOT_TOKEN=...
export SLACK_API_BASE_URL=https://slack.com/api
```

Notes:

- `MEMORY_SERVER_URL` must be an HTTP URL pointing at the MCP server endpoint
- Slack settings must be provided together or omitted together
- Langfuse can be enabled through the SDK's standard environment-based configuration
- integration tests use `TEST_DATABASE_URL`

## Running

### Start the MCP memory server

```bash
PYTHONPATH=app python -m memory_server.main
```

Equivalent project script:

```bash
memory-server
```

The server uses Streamable HTTP and publishes the MCP tool surface used by the LangGraph backend:

- `notes.save`
- `notes.search`
- `notes.update`
- `tags.search`

### Start the backend API

```bash
PYTHONPATH=app python -m backend.main
```

Equivalent project script:

```bash
backend-server
```

The backend exposes:

- `GET /api/health`
- `POST /api/message`
- `POST /slack/events` when Slack credentials are configured

Internally, `POST /api/message` runs:

- intent classification
- structured input extraction
- a LangGraph workflow for the selected intent
- Langfuse tracing around orchestration and LLM generations
- one or more MCP tool calls to the memory server

When Slack is enabled, `/slack/events` adds:

- Slack request signature verification
- event filtering and deduplication
- message formatting and reply delivery back to Slack

## Example Requests

### Backend health check

```bash
curl http://127.0.0.1:8081/api/health
```

### Backend message request

```bash
curl -X POST http://127.0.0.1:8081/api/message \
  -H 'Content-Type: application/json' \
  -d '{"text":"show notes about postgres from last week"}'
```

## Testing

Run unit tests:

```bash
PYTHONPATH=app pytest
```

Run integration tests against a dedicated PostgreSQL database:

```bash
TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/thinking_memory_hub_test PYTHONPATH=app pytest -m integration
```

Test expectations:

- unit tests do not require a live database
- integration tests are opt-in
- integration tests apply `db/schema.sql` to the test database

## Implementation Notes

Some project rules that are helpful to know before editing code:

- MCP tool handlers validate input, call exactly one storage method, and serialize output
- SQL and transactions belong in `app/memory_server/storage_client.py`
- data models and enums belong in `app/memory_server/models.py`
- configuration loading belongs in `app/memory_server/config.py`
- the backend must call the memory server through MCP rather than touching PostgreSQL directly
- backend orchestration logic belongs in LangGraph workflows rather than leaking into low-level storage code
- observability for backend LLM orchestration should stay aligned with the existing Langfuse tracing flow

## Documentation

Start with [`docs/index.md`](docs/index.md).

Additional operational docs:

- [`docs/slack_setup.md`](docs/slack_setup.md)
