# MCP Tool Definitions

## 1. Purpose

This document defines the published MCP tool definitions for the thinking memory server.

## 2. Tool Definitions

### 2.1 `notes.save`

- `name`: `notes.save`
- `description`: Save one note record.
- `input_contract`: `NoteCreateRequest`
- `output_contract`: `NoteRecord`

`inputSchema`

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["raw_text", "normalized_text", "note_kind", "created_at", "tags"],
  "properties": {
    "raw_text": { "type": "string", "minLength": 1 },
    "normalized_text": { "type": "string", "minLength": 1 },
    "note_kind": {
      "type": "string",
      "enum": ["note", "question", "task", "reading", "watch"]
    },
    "source_ref": {
      "anyOf": [
        { "type": "null" },
        { "type": "string", "minLength": 1 }
      ]
    },
    "created_at": { "type": "string", "format": "date-time" },
    "tags": {
      "type": "array",
      "items": { "type": "string", "minLength": 1 }
    }
  }
}
```

`outputSchema`

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "raw_text",
    "normalized_text",
    "note_kind",
    "created_at",
    "updated_at",
    "tags"
  ],
  "properties": {
    "id": { "type": "string", "format": "uuid" },
    "raw_text": { "type": "string", "minLength": 1 },
    "normalized_text": { "type": "string", "minLength": 1 },
    "note_kind": {
      "type": "string",
      "enum": ["note", "question", "task", "reading", "watch"]
    },
    "source_ref": {
      "anyOf": [
        { "type": "null" },
        { "type": "string", "minLength": 1 }
      ]
    },
    "created_at": { "type": "string", "format": "date-time" },
    "updated_at": { "type": "string", "format": "date-time" },
    "tags": {
      "type": "array",
      "items": { "type": "string", "minLength": 1 }
    }
  }
}
```

### 2.2 `notes.search`

- `name`: `notes.search`
- `description`: Search note records by normalized text query and filters.
- `input_contract`: `NoteSearchRequest`
- `output_contract`: `NoteList`

`inputSchema`

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["limit", "offset", "sort"],
  "properties": {
    "query": { "type": ["string", "null"] },
    "time_range": {
      "type": ["object", "null"],
      "additionalProperties": false,
      "required": ["from", "to"],
      "properties": {
        "from": { "type": "string", "format": "date-time" },
        "to": { "type": "string", "format": "date-time" }
      }
    },
    "tags": {
      "type": ["array", "null"],
      "items": { "type": "string", "minLength": 1 }
    },
    "tag_match_mode": {
      "type": ["string", "null"],
      "enum": ["any", "all", null]
    },
    "note_kinds": {
      "type": ["array", "null"],
      "items": {
        "type": "string",
        "enum": ["note", "question", "task", "reading", "watch"]
      }
    },
    "source_refs": {
      "type": ["array", "null"],
      "items": { "type": "string", "minLength": 1 }
    },
    "limit": { "type": "integer", "minimum": 1 },
    "offset": { "type": "integer", "minimum": 0 },
    "sort": {
      "type": "string",
      "enum": ["created_at_desc", "created_at_asc"]
    }
  }
}
```

`outputSchema`

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["items"],
  "properties": {
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "id",
          "raw_text",
          "normalized_text",
          "note_kind",
          "created_at",
          "updated_at",
          "tags"
        ],
        "properties": {
          "id": { "type": "string", "format": "uuid" },
          "raw_text": { "type": "string", "minLength": 1 },
          "normalized_text": { "type": "string", "minLength": 1 },
          "note_kind": {
            "type": "string",
            "enum": ["note", "question", "task", "reading", "watch"]
          },
          "source_ref": {
            "anyOf": [
              { "type": "null" },
              { "type": "string", "minLength": 1 }
            ]
          },
          "created_at": { "type": "string", "format": "date-time" },
          "updated_at": { "type": "string", "format": "date-time" },
          "tags": {
            "type": "array",
            "items": { "type": "string", "minLength": 1 }
          }
        }
      }
    }
  }
}
```

### 2.3 `notes.update`

- `name`: `notes.update`
- `description`: Update one existing note record.
- `input_contract`: `NoteUpdateRequest`
- `output_contract`: `NoteRecord`

`inputSchema`

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["note_id", "operations"],
  "properties": {
    "note_id": { "type": "string", "format": "uuid" },
    "operations": {
      "type": "array",
      "minItems": 1,
      "items": {
        "oneOf": [
          {
            "type": "object",
            "additionalProperties": false,
            "required": ["kind", "note_kind"],
            "properties": {
              "kind": { "const": "set_note_kind" },
              "note_kind": {
                "type": "string",
                "enum": ["note", "question", "task", "reading", "watch"]
              }
            }
          },
          {
            "type": "object",
            "additionalProperties": false,
            "required": ["kind", "normalized_text"],
            "properties": {
              "kind": { "const": "set_normalized_text" },
              "normalized_text": { "type": "string", "minLength": 1 }
            }
          },
          {
            "type": "object",
            "additionalProperties": false,
            "required": ["kind", "tags"],
            "properties": {
              "kind": { "const": "replace_tags" },
              "tags": {
                "type": "array",
                "items": { "type": "string", "minLength": 1 }
              }
            }
          },
          {
            "type": "object",
            "additionalProperties": false,
            "required": ["kind", "tags"],
            "properties": {
              "kind": { "const": "add_tags" },
              "tags": {
                "type": "array",
                "items": { "type": "string", "minLength": 1 }
              }
            }
          },
          {
            "type": "object",
            "additionalProperties": false,
            "required": ["kind", "tags"],
            "properties": {
              "kind": { "const": "remove_tags" },
              "tags": {
                "type": "array",
                "items": { "type": "string", "minLength": 1 }
              }
            }
          }
        ]
      }
    }
  }
}
```

`outputSchema`

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "raw_text",
    "normalized_text",
    "note_kind",
    "created_at",
    "updated_at",
    "tags"
  ],
  "properties": {
    "id": { "type": "string", "format": "uuid" },
    "raw_text": { "type": "string", "minLength": 1 },
    "normalized_text": { "type": "string", "minLength": 1 },
    "note_kind": {
      "type": "string",
      "enum": ["note", "question", "task", "reading", "watch"]
    },
    "source_ref": {
      "anyOf": [
        { "type": "null" },
        { "type": "string", "minLength": 1 }
      ]
    },
    "created_at": { "type": "string", "format": "date-time" },
    "updated_at": { "type": "string", "format": "date-time" },
    "tags": {
      "type": "array",
      "items": { "type": "string", "minLength": 1 }
    }
  }
}
```

### 2.4 `tags.search`

- `name`: `tags.search`
- `description`: Search aggregated tags derived from matching notes.
- `input_contract`: `TagSearchRequest`
- `output_contract`: `TagList`

`inputSchema`

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["limit", "offset", "sort"],
  "properties": {
    "query": { "type": ["string", "null"] },
    "time_range": {
      "type": ["object", "null"],
      "additionalProperties": false,
      "required": ["from", "to"],
      "properties": {
        "from": { "type": "string", "format": "date-time" },
        "to": { "type": "string", "format": "date-time" }
      }
    },
    "note_kinds": {
      "type": ["array", "null"],
      "items": {
        "type": "string",
        "enum": ["note", "question", "task", "reading", "watch"]
      }
    },
    "source_refs": {
      "type": ["array", "null"],
      "items": { "type": "string", "minLength": 1 }
    },
    "limit": { "type": "integer", "minimum": 1 },
    "offset": { "type": "integer", "minimum": 0 },
    "sort": {
      "type": "string",
      "enum": ["usage_count_desc", "name_asc"]
    }
  }
}
```

`outputSchema`

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["items"],
  "properties": {
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["name", "usage_count"],
        "properties": {
          "name": { "type": "string", "minLength": 1 },
          "usage_count": { "type": "integer", "minimum": 0 }
        }
      }
    }
  }
}
```
