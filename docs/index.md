# Documentation Index

## Start Here

This repository currently treats `docs/specs/` as the source of truth for implementation.

If you need to understand the project quickly, read:

1. `docs/specs/mcp_server.md`
2. `docs/specs/data_contracts.md`
3. `docs/specs/mcp_tool_definitions.md`
4. `docs/specs/storage_client_interface.md`
5. `docs/specs/backend_api.md`
6. `docs/specs/backend_server.md`
7. `docs/specs/backend_save_graph.md`
8. `docs/specs/backend_search_notes_graph.md`
9. `docs/specs/backend_intent_classifier.prompt.json`

## Current Scope

Current scope is:

- the MCP memory server for note storage and retrieval
- the backend HTTP API contract that will orchestrate requests to the memory server

Published MCP tools:

- `notes.save`
- `notes.search`
- `notes.update`
- `tags.search`

Core runtime stack:

- Python
- FastMCP
- Pydantic
- psycopg
- Postgres

## Source Of Truth

Normative documents live in `docs/specs/`:

- `docs/specs/mcp_server.md`: complete MCP server artifact contract
- `docs/specs/data_contracts.md`: canonical models, enums, and invariants
- `docs/specs/mcp_tool_definitions.md`: published MCP tool schemas
- `docs/specs/storage_client_interface.md`: storage-layer behavior and SQL boundary
- `docs/specs/backend_api.md`: backend REST API contract
- `docs/specs/backend_server.md`: complete backend server artifact contract
- `docs/specs/backend_save_graph.md`: save-note graph contract for the backend
- `docs/specs/backend_search_notes_graph.md`: search-notes graph contract for the backend
- `docs/specs/backend_intent_classifier.prompt.json`: LLM prompt and schema contract for backend intent classification

## Non-Normative Notes

`Z_tmp/` contains early exploratory notes and is not current project guidance.

If anything in `Z_tmp/` conflicts with `docs/specs/`, follow `docs/specs/`.

Additional operational notes:

- `docs/slack_setup.md`: real Slack app setup and local Slack smoke test
