CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_text TEXT NOT NULL CHECK (raw_text <> ''),
    normalized_text TEXT NOT NULL CHECK (normalized_text <> ''),
    note_kind TEXT NOT NULL CHECK (
        note_kind IN ('note', 'question', 'task', 'reading', 'watch')
    ),
    source_ref TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CHECK (source_ref IS NULL OR source_ref <> '')
);

CREATE TABLE tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE CHECK (name <> '')
);

CREATE TABLE note_tags (
    note_id UUID NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    tag_id UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (note_id, tag_id)
);

CREATE UNIQUE INDEX idx_notes_source_ref_unique
    ON notes (source_ref)
    WHERE source_ref IS NOT NULL;

CREATE INDEX idx_notes_created_at_desc
    ON notes (created_at DESC);

CREATE INDEX idx_notes_note_kind_created_at
    ON notes (note_kind, created_at DESC);

CREATE INDEX idx_notes_source_ref_created_at
    ON notes (source_ref, created_at DESC)
    WHERE source_ref IS NOT NULL;

CREATE INDEX idx_notes_normalized_text_trgm
    ON notes
    USING GIN (normalized_text gin_trgm_ops);

CREATE INDEX idx_tags_name_trgm
    ON tags
    USING GIN (name gin_trgm_ops);

CREATE INDEX idx_note_tags_tag_id_note_id
    ON note_tags (tag_id, note_id);

CREATE OR REPLACE FUNCTION set_notes_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_notes_set_updated_at
BEFORE UPDATE ON notes
FOR EACH ROW
EXECUTE FUNCTION set_notes_updated_at();
