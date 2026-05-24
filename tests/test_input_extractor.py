from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from backend.errors import InputExtractionError
from backend.input_extractor import StructuredInputExtractor


def _prompt_file(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_text(
        json.dumps(
            {
                "system_prompt": "system",
                "user_template": "User message:\n{{user_message}}\nCreated at:\n{{created_at}}",
            }
        ),
        encoding="utf-8",
    )
    return path


def _search_prompt_file(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_text(
        json.dumps(
            {
                "system_prompt": "system",
                "user_template": "User message:\n{{user_message}}",
            }
        ),
        encoding="utf-8",
    )
    return path


def _search_tags_prompt_file(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_text(
        json.dumps(
            {
                "system_prompt": "system",
                "user_template": "User message:\n{{user_message}}",
            }
        ),
        encoding="utf-8",
    )
    return path


def _update_prompt_file(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_text(
        json.dumps(
            {
                "system_prompt": "system",
                "user_template": "User message:\n{{user_message}}",
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.mark.asyncio
async def test_extract_save_input_returns_note_create_request(tmp_path: Path):
    model_client = AsyncMock()
    model_client.generate.return_value.content = json.dumps(
        {
            "raw_text": "ИИ как часть ноосферы Вернадского",
            "normalized_text": "ИИ как часть ноосферы Вернадского",
            "note_kind": "note",
            "tags": ["ai", "noosphere"],
            "source_ref": None,
        }
    )
    extractor = StructuredInputExtractor(
        model_client,
        save_prompt_path=_prompt_file(tmp_path, "save.json"),
        search_notes_prompt_path=_search_prompt_file(tmp_path, "search.json"),
        search_tags_prompt_path=_search_tags_prompt_file(tmp_path, "search_tags.json"),
        update_note_prompt_path=_update_prompt_file(tmp_path, "update.json"),
    )

    result = await extractor.extract_save_input("ИИ как часть ноосферы Вернадского")

    assert result.raw_text == "ИИ как часть ноосферы Вернадского"
    assert result.note_kind.value == "note"
    assert result.tags == ["ai", "noosphere"]
    assert result.created_at is not None


@pytest.mark.asyncio
async def test_extract_save_input_passes_schema_to_model(tmp_path: Path):
    model_client = AsyncMock()
    model_client.generate.return_value.content = json.dumps(
        {
            "raw_text": "hello",
            "normalized_text": "hello",
            "note_kind": "note",
            "tags": [],
            "source_ref": None,
        }
    )
    extractor = StructuredInputExtractor(
        model_client,
        save_prompt_path=_prompt_file(tmp_path, "save.json"),
        search_notes_prompt_path=_search_prompt_file(tmp_path, "search.json"),
        search_tags_prompt_path=_search_tags_prompt_file(tmp_path, "search_tags.json"),
        update_note_prompt_path=_update_prompt_file(tmp_path, "update.json"),
    )

    await extractor.extract_save_input("hello")

    request = model_client.generate.await_args.args[0]
    assert "raw_text" in request.response_schema["properties"]
    assert "note_kind" in request.response_schema["properties"]


@pytest.mark.asyncio
async def test_extract_search_notes_input_returns_note_search_request(tmp_path: Path):
    model_client = AsyncMock()
    model_client.generate.return_value.content = json.dumps(
        {
            "query": "MCP",
            "time_range": None,
            "tags": None,
            "tag_match_mode": None,
            "note_kinds": None,
            "source_refs": None,
            "limit": 10,
            "offset": 0,
            "sort": "created_at_desc"
        }
    )
    extractor = StructuredInputExtractor(
        model_client,
        save_prompt_path=_prompt_file(tmp_path, "save.json"),
        search_notes_prompt_path=_search_prompt_file(tmp_path, "search.json"),
        search_tags_prompt_path=_search_tags_prompt_file(tmp_path, "search_tags.json"),
        update_note_prompt_path=_update_prompt_file(tmp_path, "update.json"),
    )

    result = await extractor.extract_search_notes_input("покажи мои заметки про MCP")

    assert result.query == "MCP"
    assert result.limit == 10
    assert result.sort.value == "created_at_desc"


@pytest.mark.asyncio
async def test_extract_search_notes_input_derives_today_time_range(tmp_path: Path):
    model_client = AsyncMock()
    model_client.generate.return_value.content = json.dumps(
        {
            "query": None,
            "time_range": None,
            "tags": None,
            "tag_match_mode": None,
            "note_kinds": None,
            "source_refs": None,
            "limit": 10,
            "offset": 0,
            "sort": "created_at_desc",
        }
    )
    extractor = StructuredInputExtractor(
        model_client,
        save_prompt_path=_prompt_file(tmp_path, "save.json"),
        search_notes_prompt_path=_search_prompt_file(tmp_path, "search.json"),
        search_tags_prompt_path=_search_tags_prompt_file(tmp_path, "search_tags.json"),
        update_note_prompt_path=_update_prompt_file(tmp_path, "update.json"),
    )

    result = await extractor.extract_search_notes_input("what notes i saved today?")

    assert result.time_range is not None
    assert result.time_range.from_.date() == result.time_range.to.date()


@pytest.mark.asyncio
async def test_extract_search_notes_input_derives_this_week_time_range(tmp_path: Path):
    model_client = AsyncMock()
    model_client.generate.return_value.content = json.dumps(
        {
            "query": None,
            "time_range": None,
            "tags": None,
            "tag_match_mode": None,
            "note_kinds": None,
            "source_refs": None,
            "limit": 10,
            "offset": 0,
            "sort": "created_at_desc",
        }
    )
    extractor = StructuredInputExtractor(
        model_client,
        save_prompt_path=_prompt_file(tmp_path, "save.json"),
        search_notes_prompt_path=_search_prompt_file(tmp_path, "search.json"),
        search_tags_prompt_path=_search_tags_prompt_file(tmp_path, "search_tags.json"),
        update_note_prompt_path=_update_prompt_file(tmp_path, "update.json"),
    )

    result = await extractor.extract_search_notes_input("what notes i saved this week?")

    assert result.time_range is not None
    assert result.time_range.from_.weekday() == 0


@pytest.mark.asyncio
async def test_extract_search_notes_input_rejects_invalid_json(tmp_path: Path):
    model_client = AsyncMock()
    model_client.generate.return_value.content = "not json"
    extractor = StructuredInputExtractor(
        model_client,
        save_prompt_path=_prompt_file(tmp_path, "save.json"),
        search_notes_prompt_path=_search_prompt_file(tmp_path, "search.json"),
        search_tags_prompt_path=_search_tags_prompt_file(tmp_path, "search_tags.json"),
        update_note_prompt_path=_update_prompt_file(tmp_path, "update.json"),
    )

    with pytest.raises(InputExtractionError):
        await extractor.extract_search_notes_input("hello")

    assert model_client.generate.await_count == 2


@pytest.mark.asyncio
async def test_extract_search_notes_input_retries_after_invalid_json(tmp_path: Path):
    model_client = AsyncMock()
    model_client.generate.side_effect = [
        type("Response", (), {"content": "not json"})(),
        type(
            "Response",
            (),
            {
                "content": json.dumps(
                    {
                        "query": None,
                        "time_range": None,
                        "tags": ["mcp", "memory"],
                        "tag_match_mode": "all",
                        "note_kinds": None,
                        "source_refs": None,
                        "limit": 10,
                        "offset": 0,
                        "sort": "created_at_desc",
                    }
                )
            },
        )(),
    ]
    extractor = StructuredInputExtractor(
        model_client,
        save_prompt_path=_prompt_file(tmp_path, "save.json"),
        search_notes_prompt_path=_search_prompt_file(tmp_path, "search.json"),
        search_tags_prompt_path=_search_tags_prompt_file(tmp_path, "search_tags.json"),
        update_note_prompt_path=_update_prompt_file(tmp_path, "update.json"),
    )

    result = await extractor.extract_search_notes_input("найди заметки с тегами mcp и memory")

    assert result.tags == ["mcp", "memory"]
    assert result.tag_match_mode.value == "all"
    assert model_client.generate.await_count == 2


@pytest.mark.asyncio
async def test_extract_save_input_rejects_invalid_payload(tmp_path: Path):
    model_client = AsyncMock()
    model_client.generate.return_value.content = json.dumps(
        {
            "raw_text": "",
            "normalized_text": "",
            "note_kind": "note",
            "tags": [],
            "source_ref": None,
        }
    )
    extractor = StructuredInputExtractor(
        model_client,
        save_prompt_path=_prompt_file(tmp_path, "save.json"),
        search_notes_prompt_path=_search_prompt_file(tmp_path, "search.json"),
        search_tags_prompt_path=_search_tags_prompt_file(tmp_path, "search_tags.json"),
        update_note_prompt_path=_update_prompt_file(tmp_path, "update.json"),
    )

    with pytest.raises(InputExtractionError):
        await extractor.extract_save_input("hello")


@pytest.mark.asyncio
async def test_extract_search_tags_input_returns_tag_search_request(tmp_path: Path):
    model_client = AsyncMock()
    model_client.generate.return_value.content = json.dumps(
        {
            "query": "AI",
            "time_range": None,
            "note_kinds": None,
            "source_refs": None,
            "limit": 10,
            "offset": 0,
            "sort": "usage_count_desc",
        }
    )
    extractor = StructuredInputExtractor(
        model_client,
        save_prompt_path=_prompt_file(tmp_path, "save.json"),
        search_notes_prompt_path=_search_prompt_file(tmp_path, "search.json"),
        search_tags_prompt_path=_search_tags_prompt_file(tmp_path, "search_tags.json"),
        update_note_prompt_path=_update_prompt_file(tmp_path, "update.json"),
    )

    result = await extractor.extract_search_tags_input("какие у меня были темы по AI")

    assert result.query == "AI"
    assert result.limit == 10
    assert result.sort.value == "usage_count_desc"


@pytest.mark.asyncio
async def test_extract_update_note_input_returns_update_extraction_result(tmp_path: Path):
    model_client = AsyncMock()
    model_client.generate.return_value.content = json.dumps(
        {
            "target_mode": "latest_note",
            "operations": [
                {"kind": "set_note_kind", "note_kind": "task"}
            ],
        }
    )
    extractor = StructuredInputExtractor(
        model_client,
        save_prompt_path=_prompt_file(tmp_path, "save.json"),
        search_notes_prompt_path=_search_prompt_file(tmp_path, "search.json"),
        search_tags_prompt_path=_search_tags_prompt_file(tmp_path, "search_tags.json"),
        update_note_prompt_path=_update_prompt_file(tmp_path, "update.json"),
    )

    result = await extractor.extract_update_note_input("исправь тип последней заметки на task")

    assert result.target_mode.value == "latest_note"
    assert result.operations[0].kind.value == "set_note_kind"
