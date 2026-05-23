from __future__ import annotations

import logging
from uuid import UUID

import psycopg
import psycopg.errors
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from memory_server.errors import StorageClientError, StorageConflictError, StorageNotFoundError
from memory_server.models import (
    AddTagsOperation,
    NoteCreateRequest,
    NoteKind,
    NoteList,
    NoteRecord,
    NoteSearchRequest,
    NoteSearchSort,
    NoteUpdateOperation,
    NoteUpdateRequest,
    RemoveTagsOperation,
    ReplaceTagsOperation,
    SetNoteKindOperation,
    SetNormalizedTextOperation,
    TagList,
    TagMatchMode,
    TagSearchRequest,
    TagSearchResult,
    TagSearchSort,
)


logger = logging.getLogger(__name__)


class StorageClient:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._pool: AsyncConnectionPool | None = None

    async def open(self) -> None:
        logger.info("Initializing AsyncConnectionPool")
        self._pool = AsyncConnectionPool(self._database_url, open=False)
        logger.info("Opening AsyncConnectionPool")
        await self._pool.open()
        logger.info("AsyncConnectionPool opened")

    async def close(self) -> None:
        if self._pool is not None:
            logger.info("Closing AsyncConnectionPool")
            await self._pool.close()
            self._pool = None
            logger.info("AsyncConnectionPool closed")

    def _get_pool(self) -> AsyncConnectionPool:
        if self._pool is None:
            raise StorageClientError("StorageClient is not open")
        return self._pool

    async def create_note(self, request: NoteCreateRequest) -> NoteRecord:
        pool = self._get_pool()
        try:
            async with pool.connection() as conn:
                async with conn.transaction():
                    async with conn.cursor(row_factory=dict_row) as cur:
                        await cur.execute(
                            """
                            INSERT INTO notes (raw_text, normalized_text, note_kind, source_ref, created_at, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            RETURNING id, raw_text, normalized_text, note_kind, source_ref, created_at, updated_at
                            """,
                            (
                                request.raw_text,
                                request.normalized_text,
                                request.note_kind.value,
                                request.source_ref,
                                request.created_at,
                                request.created_at,
                            ),
                        )
                        row = await cur.fetchone()
                    note_id: UUID = row["id"]
                    stored_tags = await _upsert_tags_and_link(conn, note_id, request.tags)
                    return _build_note_record(row, stored_tags)
        except psycopg.errors.UniqueViolation:
            raise StorageConflictError("source_ref uniqueness constraint violated")
        except (StorageClientError, StorageConflictError):
            raise
        except Exception as exc:
            raise StorageClientError(str(exc)) from exc

    async def search_notes(self, request: NoteSearchRequest) -> NoteList:
        if request.tags is not None and request.tag_match_mode is None:
            raise StorageClientError("tag_match_mode is required when tags filter is present")

        pool = self._get_pool()
        try:
            async with pool.connection() as conn:
                conditions: list[str] = []
                params: list[object] = []

                if request.query is not None:
                    conditions.append("n.normalized_text %% %s")
                    params.append(request.query)

                if request.time_range is not None:
                    conditions.append("n.created_at >= %s AND n.created_at <= %s")
                    params.extend([request.time_range.from_, request.time_range.to])

                if request.note_kinds is not None:
                    conditions.append("n.note_kind = ANY(%s::text[])")
                    params.append([k.value for k in request.note_kinds])

                if request.source_refs is not None:
                    conditions.append("n.source_ref = ANY(%s)")
                    params.append(request.source_refs)

                if request.tags is not None:
                    tag_subquery, tag_params = _build_tag_filter_subquery(
                        request.tags, request.tag_match_mode
                    )
                    conditions.append(tag_subquery)
                    params.extend(tag_params)

                where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

                if request.query is not None:
                    # params[0] already holds query for the %% filter in WHERE.
                    # select_extra adds one more placeholder for similarity(), prepended here.
                    select_extra = ", similarity(n.normalized_text, %s) AS _sim"
                    order_clause = _build_similarity_order(request.sort)
                    final_params = [request.query] + params + [request.limit, request.offset]
                else:
                    select_extra = ""
                    order_clause = _build_sort_order(request.sort)
                    final_params = params + [request.limit, request.offset]

                sql = f"""
                    SELECT
                        n.id, n.raw_text, n.normalized_text, n.note_kind,
                        n.source_ref, n.created_at, n.updated_at
                        {select_extra}
                    FROM notes n
                    {where_clause}
                    {order_clause}
                    LIMIT %s OFFSET %s
                """

                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(sql, final_params)
                    rows = await cur.fetchall()

                note_ids = [r["id"] for r in rows]
                tags_map = await _fetch_tags_for_notes(conn, note_ids)
                items = [_build_note_record(r, tags_map.get(r["id"], [])) for r in rows]
                return NoteList(items=items)
        except StorageClientError:
            raise
        except Exception as exc:
            raise StorageClientError(str(exc)) from exc

    async def update_note(self, request: NoteUpdateRequest) -> NoteRecord:
        pool = self._get_pool()
        try:
            async with pool.connection() as conn:
                async with conn.transaction():
                    async with conn.cursor(row_factory=dict_row) as cur:
                        await cur.execute(
                            "SELECT id FROM notes WHERE id = %s FOR UPDATE",
                            (request.note_id,),
                        )
                        existing = await cur.fetchone()

                    if existing is None:
                        raise StorageNotFoundError(f"Note {request.note_id} not found")

                    set_clauses: list[str] = []
                    set_params: list[object] = []
                    for op in request.operations:
                        _apply_scalar_op(op, set_clauses, set_params)

                    if set_clauses:
                        set_params.append(request.note_id)
                        async with conn.cursor() as cur:
                            await cur.execute(
                                f"UPDATE notes SET {', '.join(set_clauses)} WHERE id = %s",
                                set_params,
                            )

                    for op in request.operations:
                        await _apply_tag_op(conn, request.note_id, op)

                    async with conn.cursor(row_factory=dict_row) as cur:
                        await cur.execute(
                            """
                            SELECT id, raw_text, normalized_text, note_kind,
                                   source_ref, created_at, updated_at
                            FROM notes WHERE id = %s
                            """,
                            (request.note_id,),
                        )
                        row = await cur.fetchone()

                    tags_map = await _fetch_tags_for_notes(conn, [request.note_id])
                    return _build_note_record(row, tags_map.get(request.note_id, []))
        except (StorageNotFoundError, StorageClientError):
            raise
        except Exception as exc:
            raise StorageClientError(str(exc)) from exc

    async def search_tags(self, request: TagSearchRequest) -> TagList:
        pool = self._get_pool()
        try:
            async with pool.connection() as conn:
                note_conditions: list[str] = []
                params: list[object] = []

                if request.time_range is not None:
                    note_conditions.append("n.created_at >= %s AND n.created_at <= %s")
                    params.extend([request.time_range.from_, request.time_range.to])

                if request.note_kinds is not None:
                    note_conditions.append("n.note_kind = ANY(%s::text[])")
                    params.append([k.value for k in request.note_kinds])

                if request.source_refs is not None:
                    note_conditions.append("n.source_ref = ANY(%s)")
                    params.append(request.source_refs)

                note_where = ("WHERE " + " AND ".join(note_conditions)) if note_conditions else ""

                tag_condition = ""
                if request.query is not None:
                    tag_condition = "AND t.name %% %s"
                    params.append(request.query)

                order_clause = _build_tag_sort_order(request.sort)

                sql = f"""
                    SELECT t.name, COUNT(DISTINCT nt.note_id) AS usage_count
                    FROM tags t
                    JOIN note_tags nt ON nt.tag_id = t.id
                    JOIN notes n ON n.id = nt.note_id
                    {note_where}
                    {tag_condition}
                    GROUP BY t.name
                    {order_clause}
                    LIMIT %s OFFSET %s
                """
                params.extend([request.limit, request.offset])

                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(sql, params)
                    rows = await cur.fetchall()

                items = [
                    TagSearchResult(name=r["name"], usage_count=r["usage_count"]) for r in rows
                ]
                return TagList(items=items)
        except StorageClientError:
            raise
        except Exception as exc:
            raise StorageClientError(str(exc)) from exc


# ── helpers ──────────────────────────────────────────────────────────────────


async def _upsert_tags_and_link(
    conn: psycopg.AsyncConnection, note_id: UUID, tags: list[str]
) -> list[str]:
    if not tags:
        return []
    async with conn.cursor() as cur:
        for tag in tags:
            await cur.execute(
                "INSERT INTO tags (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                (tag,),
            )
        await cur.execute(
            """
            INSERT INTO note_tags (note_id, tag_id)
            SELECT %s, id FROM tags WHERE name = ANY(%s)
            ON CONFLICT DO NOTHING
            """,
            (note_id, tags),
        )
    return tags


async def _fetch_tags_for_notes(
    conn: psycopg.AsyncConnection, note_ids: list[UUID]
) -> dict[UUID, list[str]]:
    if not note_ids:
        return {}
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT nt.note_id, t.name
            FROM note_tags nt
            JOIN tags t ON t.id = nt.tag_id
            WHERE nt.note_id = ANY(%s)
            """,
            (note_ids,),
        )
        rows = await cur.fetchall()
    result: dict[UUID, list[str]] = {}
    for row in rows:
        result.setdefault(row["note_id"], []).append(row["name"])
    return result


def _build_note_record(row: dict, tags: list[str]) -> NoteRecord:
    return NoteRecord(
        id=row["id"],
        raw_text=row["raw_text"],
        normalized_text=row["normalized_text"],
        note_kind=NoteKind(row["note_kind"]),
        source_ref=row["source_ref"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        tags=tags,
    )


def _build_tag_filter_subquery(
    tags: list[str], mode: TagMatchMode
) -> tuple[str, list[object]]:
    if mode == TagMatchMode.any:
        return (
            "n.id IN (SELECT note_id FROM note_tags nt JOIN tags t ON t.id = nt.tag_id WHERE t.name = ANY(%s))",
            [tags],
        )
    return (
        """
        n.id IN (
            SELECT nt.note_id
            FROM note_tags nt
            JOIN tags t ON t.id = nt.tag_id
            WHERE t.name = ANY(%s)
            GROUP BY nt.note_id
            HAVING COUNT(DISTINCT t.name) = %s
        )
        """,
        [tags, len(tags)],
    )


def _build_sort_order(sort: NoteSearchSort) -> str:
    if sort == NoteSearchSort.created_at_desc:
        return "ORDER BY n.created_at DESC"
    return "ORDER BY n.created_at ASC"


def _build_similarity_order(sort: NoteSearchSort) -> str:
    tiebreak = "n.created_at DESC" if sort == NoteSearchSort.created_at_desc else "n.created_at ASC"
    return f"ORDER BY _sim DESC, {tiebreak}"


def _build_tag_sort_order(sort: TagSearchSort) -> str:
    if sort == TagSearchSort.usage_count_desc:
        return "ORDER BY usage_count DESC"
    return "ORDER BY t.name ASC"


def _apply_scalar_op(
    op: NoteUpdateOperation, set_clauses: list[str], params: list[object]
) -> None:
    if isinstance(op, SetNoteKindOperation):
        set_clauses.append("note_kind = %s")
        params.append(op.note_kind.value)
    elif isinstance(op, SetNormalizedTextOperation):
        set_clauses.append("normalized_text = %s")
        params.append(op.normalized_text)


async def _apply_tag_op(
    conn: psycopg.AsyncConnection, note_id: UUID, op: NoteUpdateOperation
) -> None:
    if isinstance(op, ReplaceTagsOperation):
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM note_tags WHERE note_id = %s", (note_id,))
        if op.tags:
            await _upsert_tags_and_link(conn, note_id, op.tags)
    elif isinstance(op, AddTagsOperation):
        if op.tags:
            await _upsert_tags_and_link(conn, note_id, op.tags)
    elif isinstance(op, RemoveTagsOperation):
        if op.tags:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    DELETE FROM note_tags
                    WHERE note_id = %s
                      AND tag_id IN (SELECT id FROM tags WHERE name = ANY(%s))
                    """,
                    (note_id, op.tags),
                )
