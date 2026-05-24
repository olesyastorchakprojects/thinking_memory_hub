# Data Contracts

## 1. Purpose

This document defines the canonical data types used by the thinking memory system.

This document defines:

- stored record types
- request types
- response types
- enum values
- field-level invariants

All field types in this document are normative.

## 2. Canonical Enums

### 2.1 `NoteKind`

Allowed values:

- `note`
- `question`
- `task`
- `reading`
- `watch`

### 2.2 `TagMatchMode`

Allowed values:

- `any`
- `all`

### 2.3 `NoteSearchSort`

Allowed values:

- `created_at_desc`
- `created_at_asc`

### 2.4 `TagSearchSort`

Allowed values:

- `usage_count_desc`
- `name_asc`

### 2.5 `NoteUpdateOperationKind`

Allowed values:

- `set_note_kind`
- `set_normalized_text`
- `replace_tags`
- `add_tags`
- `remove_tags`

## 3. Stored Record Types

### 3.1 `NoteRecord`

Canonical shape:

```yaml
id: uuid
raw_text: string
normalized_text: string
note_kind: NoteKind
source_ref: string | null
created_at: datetime
updated_at: datetime
tags: string[]
```

Field requirements:

- `id` is the canonical note identifier and must be a UUID.
- `raw_text` is required and must be non-empty.
- `normalized_text` is required and must be non-empty.
- `note_kind` is required and must be one of `NoteKind`.
- `source_ref` is nullable.
- `source_ref`, when present, must be non-empty.
- `created_at` is required.
- `updated_at` is required.
- `tags` is required and may be empty.
- every tag value in `tags` must be non-empty.

## 4. Shared Value Types

### 4.1 `TimeRange`

Canonical shape:

```yaml
from: datetime
to: datetime
```

Field requirements:

- `from` is required.
- `to` is required.
- `from` must be less than or equal to `to`.

## 5. Request Types

### 5.1 `NoteCreateRequest`

Canonical shape:

```yaml
raw_text: string
normalized_text: string
note_kind: NoteKind
source_ref: string | null
created_at: datetime
tags: string[]
```

Field requirements:

- `raw_text` is required and must be non-empty.
- `normalized_text` is required and must be non-empty.
- `note_kind` is required and must be one of `NoteKind`.
- `source_ref` is nullable.
- `source_ref`, when present, must be non-empty.
- `created_at` is required.
- `tags` is required and may be empty.
- every tag value in `tags` must be non-empty.

### 5.2 `NoteSearchRequest`

Canonical shape:

```yaml
query: string | null
time_range: TimeRange | null
tags: string[] | null
tag_match_mode: TagMatchMode | null
note_kinds: NoteKind[] | null
source_refs: string[] | null
limit: integer
offset: integer
sort: NoteSearchSort
```

Field requirements:

- `query` is nullable.
- `time_range` is nullable.
- `tags` is nullable.
- `tag_match_mode` is nullable and must be one of `TagMatchMode` when present.
- `note_kinds` is nullable.
- `source_refs` is nullable.
- `limit` is required and must be greater than `0`.
- `offset` is required and must be greater than or equal to `0`.
- `sort` is required and must be one of `NoteSearchSort`.

### 5.3 `TagSearchRequest`

Canonical shape:

```yaml
query: string | null
time_range: TimeRange | null
note_kinds: NoteKind[] | null
source_refs: string[] | null
limit: integer
offset: integer
sort: TagSearchSort
```

Field requirements:

- `query` is nullable.
- `time_range` is nullable.
- `note_kinds` is nullable.
- `source_refs` is nullable.
- `limit` is required and must be greater than `0`.
- `offset` is required and must be greater than or equal to `0`.
- `sort` is required and must be one of `TagSearchSort`.

### 5.4 `NoteUpdateRequest`

Canonical shape:

```yaml
note_id: uuid
operations: NoteUpdateOperation[]
```

Field requirements:

- `note_id` is required and must be a UUID.
- `operations` is required.
- `operations` must contain at least one operation.

### 5.5 `NoteUpdateOperation`

`NoteUpdateOperation` is a tagged union.

Allowed variants:

#### 5.5.1 `SetNoteKindOperation`

```yaml
kind: set_note_kind
note_kind: NoteKind
```

#### 5.5.2 `SetNormalizedTextOperation`

```yaml
kind: set_normalized_text
normalized_text: string
```

Rules:

- `normalized_text` must be non-empty.

#### 5.5.3 `ReplaceTagsOperation`

```yaml
kind: replace_tags
tags: string[]
```

Rules:

- every tag value in `tags` must be non-empty.

#### 5.5.4 `AddTagsOperation`

```yaml
kind: add_tags
tags: string[]
```

Rules:

- every tag value in `tags` must be non-empty.

#### 5.5.5 `RemoveTagsOperation`

```yaml
kind: remove_tags
tags: string[]
```

Rules:

- every tag value in `tags` must be non-empty.

## 6. Response Types

### 6.1 `NoteList`

Canonical shape:

```yaml
items: NoteRecord[]
```

Field requirements:

- `items` is required.
- `items` contains zero or more `NoteRecord` values.

### 6.2 `TagSearchResult`

Canonical shape:

```yaml
name: string
usage_count: integer
```

Field requirements:

- `name` is required and must be non-empty.
- `usage_count` is required and must be greater than or equal to `0`.

### 6.3 `TagList`

Canonical shape:

```yaml
items: TagSearchResult[]
```

Field requirements:

- `items` is required.
- `items` contains zero or more `TagSearchResult` values.

## 7. Search Semantics

- `NoteSearchRequest` applies all present filters together.
- `query`, when present, is combined with all present filters.
- `NoteSearchRequest.query`, when present, searches note `normalized_text`.
- `tags`, when present, use `tag_match_mode`.
- when `tags` is present and `tag_match_mode` is absent, the request is invalid.
- `TagSearchRequest` applies all present filters together.
- `TagSearchRequest.query`, when present, filters tag names.
- `TagSearchRequest.time_range`, when present, restricts the note set used for tag aggregation.
- `TagSearchRequest.note_kinds`, when present, restricts the note set used for tag aggregation.
- `TagSearchRequest.source_refs`, when present, restricts the note set used for tag aggregation.
