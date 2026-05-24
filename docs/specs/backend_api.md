# Backend API

## 1. Purpose

This document defines the HTTP API contract for the thinking memory backend.

This document defines:

- the published REST endpoints
- endpoint request and response types
- allowed error responses
- the intent values returned by the backend

The backend defined by this document is the orchestration layer that accepts
user input, interprets intent, invokes the remote MCP memory server, and
returns a user-facing response.

## 2. Scope

The backend publishes exactly two HTTP endpoints in `v1`:

- `GET /api/health`
- `POST /api/message`

No other public REST endpoints are defined by this document.

## 3. Shared Enums

### 3.1 `BackendIntent`

Allowed values:

- `save_note`
- `search_notes`
- `search_tags`
- `update_note`

### 3.2 `BackendErrorCode`

Allowed values:

- `invalid_request`
- `intent_parse_failed`
- `backend_processing_failed`
- `memory_server_error`

## 4. Endpoint Contracts

### 4.1 `GET /api/health`

#### Response Type: `HealthResponse`

Canonical shape:

```yaml
status: string
```

Field requirements:

- `status` is required.
- `status` must be exactly `ok`.

Example:

```json
{
  "status": "ok"
}
```

### 4.2 `POST /api/message`

#### Request Type: `MessageRequest`

Canonical shape:

```yaml
text: string
```

Field requirements:

- `text` is required.
- `text` must be non-empty.

Example:

```json
{
  "text": "покажи, что я сохраняла за последнюю неделю"
}
```

#### Response Type: `MessageResponse`

Canonical shape:

```yaml
message: string
intent: BackendIntent
result: MessageResult
```

Field requirements:

- `message` is required and must be non-empty.
- `intent` is required and must be one of `BackendIntent`.
- `result` is required.

## 5. Message Result Types

### 5.1 `MessageResult`

`MessageResult` is a tagged union selected by `MessageResponse.intent`.

Allowed variants:

- `SaveNoteResult`
- `SearchNotesResult`
- `SearchTagsResult`
- `UpdateNoteResult`

### 5.2 `SaveNoteResult`

Canonical shape:

```yaml
note: NoteRecord
```

Field requirements:

- `note` is required.
- `note` must match `NoteRecord` from `docs/specs/data_contracts.md`.

### 5.3 `SearchNotesResult`

Canonical shape:

```yaml
notes: NoteRecord[]
```

Field requirements:

- `notes` is required.
- each item in `notes` must match `NoteRecord` from `docs/specs/data_contracts.md`.

### 5.4 `SearchTagsResult`

Canonical shape:

```yaml
tags: TagSearchResult[]
```

Field requirements:

- `tags` is required.
- each item in `tags` must match `TagSearchResult` from `docs/specs/data_contracts.md`.

### 5.5 `UpdateNoteResult`

Canonical shape:

```yaml
note: NoteRecord
```

Field requirements:

- `note` is required.
- `note` must match `NoteRecord` from `docs/specs/data_contracts.md`.

## 6. Error Response Contract

### 6.1 `ErrorResponse`

Canonical shape:

```yaml
error:
  code: BackendErrorCode
  message: string
```

Field requirements:

- `error` is required.
- `error.code` is required and must be one of `BackendErrorCode`.
- `error.message` is required and must be non-empty.

Example:

```json
{
  "error": {
    "code": "invalid_request",
    "message": "Field 'text' is required."
  }
}
```

## 7. Response Semantics

### 7.1 `GET /api/health`

- must return HTTP `200`
- must return `HealthResponse`

### 7.2 `POST /api/message`

- must return HTTP `200` on successful processing
- must return `MessageResponse` on success
- must return `ErrorResponse` on failure

### 7.3 Intent-to-Result Mapping

The backend must return the following result shape for each intent:

- `save_note` -> `SaveNoteResult`
- `search_notes` -> `SearchNotesResult`
- `search_tags` -> `SearchTagsResult`
- `update_note` -> `UpdateNoteResult`

## 8. Backend Orchestration Boundary

The backend defined by this document:

- accepts natural-language user input through `POST /api/message`
- determines one `BackendIntent`
- invokes the remote MCP memory server
- returns a user-facing `message`
- returns the structured backend result in `result`

The backend defined by this document does not:

- access PostgreSQL directly
- implement note storage locally
- expose MCP tools directly

