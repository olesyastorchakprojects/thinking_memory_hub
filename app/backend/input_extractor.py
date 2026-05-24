from __future__ import annotations

import json
import re
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from backend.errors import InputExtractionError
from backend.model_client import ModelClient
from backend.models import (
    ModelGenerationRequest,
    ModelMessage,
    ModelMessageRole,
    SaveExtractionResult,
    UpdateExtractionResult,
)
from memory_server.models import NoteCreateRequest, NoteSearchRequest, TagSearchRequest, TimeRange


class StructuredInputExtractor:
    _MAX_RETRIES = 2
    _TODAY_RE = re.compile(r"\b(today|сегодня)\b", re.IGNORECASE)
    _YESTERDAY_RE = re.compile(r"\b(yesterday|вчера)\b", re.IGNORECASE)
    _THIS_WEEK_RE = re.compile(r"\b(this week|на этой неделе|за эту неделю)\b", re.IGNORECASE)
    _LAST_WEEK_RE = re.compile(r"\b(last week|на прошлой неделе|за прошлую неделю)\b", re.IGNORECASE)

    def __init__(
        self,
        model_client: ModelClient,
        *,
        save_prompt_path: Path | None = None,
        search_notes_prompt_path: Path | None = None,
        search_tags_prompt_path: Path | None = None,
        update_note_prompt_path: Path | None = None,
    ) -> None:
        base = Path(__file__).resolve().parents[2] / "docs" / "specs"
        self._model_client = model_client
        self._save_prompt = self._load_prompt_spec(
            save_prompt_path or (base / "backend_save_input_extractor.prompt.json")
        )
        self._search_notes_prompt = self._load_prompt_spec(
            search_notes_prompt_path or (base / "backend_search_notes_input_extractor.prompt.json")
        )
        self._search_tags_prompt = self._load_prompt_spec(
            search_tags_prompt_path or (base / "backend_search_tags_input_extractor.prompt.json")
        )
        self._update_note_prompt = self._load_prompt_spec(
            update_note_prompt_path or (base / "backend_update_note_input_extractor.prompt.json")
        )

    async def extract_save_input(self, user_message: str) -> NoteCreateRequest:
        if not user_message.strip():
            raise InputExtractionError("user message must be non-empty")

        created_at = datetime.now(timezone.utc).isoformat()
        request = ModelGenerationRequest(
            messages=[
                ModelMessage(
                    role=ModelMessageRole.system,
                    content=self._save_prompt["system_prompt"],
                ),
                ModelMessage(
                    role=ModelMessageRole.user,
                    content=self._save_prompt["user_template"]
                    .replace("{{user_message}}", user_message)
                    .replace("{{created_at}}", created_at),
                ),
            ],
            temperature=0.0,
            max_output_tokens=1000,
            response_schema=SaveExtractionResult.model_json_schema(),
        )
        payload = await self._generate_payload(request, "save extractor")
        try:
            extracted = SaveExtractionResult.model_validate(payload)
        except Exception as exc:
            raise InputExtractionError("save extractor returned invalid payload") from exc

        try:
            return NoteCreateRequest(
                raw_text=extracted.raw_text,
                normalized_text=extracted.normalized_text,
                note_kind=extracted.note_kind,
                source_ref=extracted.source_ref,
                created_at=created_at,
                tags=extracted.tags,
            )
        except Exception as exc:
            raise InputExtractionError("save extractor payload cannot build NoteCreateRequest") from exc

    async def extract_search_notes_input(self, user_message: str) -> NoteSearchRequest:
        if not user_message.strip():
            raise InputExtractionError("user message must be non-empty")

        request = ModelGenerationRequest(
            messages=[
                ModelMessage(
                    role=ModelMessageRole.system,
                    content=self._search_notes_prompt["system_prompt"],
                ),
                ModelMessage(
                    role=ModelMessageRole.user,
                    content=self._search_notes_prompt["user_template"].replace(
                        "{{user_message}}", user_message
                    ),
                ),
            ],
            temperature=0.0,
            max_output_tokens=1000,
            response_schema=NoteSearchRequest.model_json_schema(by_alias=True),
        )
        payload = await self._generate_payload(request, "search-notes extractor")
        try:
            extracted = NoteSearchRequest.model_validate(payload)
        except Exception as exc:
            raise InputExtractionError("search-notes extractor returned invalid payload") from exc
        return self._apply_relative_time_range(user_message, extracted)

    async def extract_search_tags_input(self, user_message: str) -> TagSearchRequest:
        if not user_message.strip():
            raise InputExtractionError("user message must be non-empty")

        request = ModelGenerationRequest(
            messages=[
                ModelMessage(
                    role=ModelMessageRole.system,
                    content=self._search_tags_prompt["system_prompt"],
                ),
                ModelMessage(
                    role=ModelMessageRole.user,
                    content=self._search_tags_prompt["user_template"].replace(
                        "{{user_message}}", user_message
                    ),
                ),
            ],
            temperature=0.0,
            max_output_tokens=1000,
            response_schema=TagSearchRequest.model_json_schema(by_alias=True),
        )
        payload = await self._generate_payload(request, "search-tags extractor")
        try:
            extracted = TagSearchRequest.model_validate(payload)
        except Exception as exc:
            raise InputExtractionError("search-tags extractor returned invalid payload") from exc
        return self._apply_relative_tag_time_range(user_message, extracted)

    async def extract_update_note_input(self, user_message: str) -> UpdateExtractionResult:
        if not user_message.strip():
            raise InputExtractionError("user message must be non-empty")

        request = ModelGenerationRequest(
            messages=[
                ModelMessage(
                    role=ModelMessageRole.system,
                    content=self._update_note_prompt["system_prompt"],
                ),
                ModelMessage(
                    role=ModelMessageRole.user,
                    content=self._update_note_prompt["user_template"].replace(
                        "{{user_message}}", user_message
                    ),
                ),
            ],
            temperature=0.0,
            max_output_tokens=1000,
            response_schema=UpdateExtractionResult.model_json_schema(),
        )
        payload = await self._generate_payload(request, "update-note extractor")
        try:
            return UpdateExtractionResult.model_validate(payload)
        except Exception as exc:
            raise InputExtractionError("update-note extractor returned invalid payload") from exc

    async def _generate_payload(self, request: ModelGenerationRequest, label: str) -> dict:
        last_error: InputExtractionError | None = None
        for _ in range(self._MAX_RETRIES):
            response = await self._model_client.generate(request)
            try:
                return self._parse_json_payload(response.content, label)
            except InputExtractionError as exc:
                last_error = exc
        assert last_error is not None
        raise last_error

    @staticmethod
    def _parse_json_payload(content: str, label: str) -> dict:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise InputExtractionError(f"{label} returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise InputExtractionError(f"{label} returned non-object payload")
        return payload

    @classmethod
    def _apply_relative_time_range(
        cls,
        user_message: str,
        request: NoteSearchRequest,
    ) -> NoteSearchRequest:
        if request.time_range is not None:
            return request
        derived = cls._derive_relative_time_range(user_message)
        if derived is None:
            return request
        return request.model_copy(update={"time_range": TimeRange.model_validate(derived)})

    @classmethod
    def _apply_relative_tag_time_range(
        cls,
        user_message: str,
        request: TagSearchRequest,
    ) -> TagSearchRequest:
        if request.time_range is not None:
            return request
        derived = cls._derive_relative_time_range(user_message)
        if derived is None:
            return request
        return request.model_copy(update={"time_range": TimeRange.model_validate(derived)})

    @classmethod
    def _derive_relative_time_range(cls, user_message: str) -> dict[str, str] | None:
        text = user_message.strip()
        if not text:
            return None

        now = datetime.now().astimezone()
        if cls._TODAY_RE.search(text):
            start = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
            end = datetime.combine(now.date(), time.max, tzinfo=now.tzinfo)
            return {"from": start.isoformat(), "to": end.isoformat()}

        if cls._YESTERDAY_RE.search(text):
            day = now.date() - timedelta(days=1)
            start = datetime.combine(day, time.min, tzinfo=now.tzinfo)
            end = datetime.combine(day, time.max, tzinfo=now.tzinfo)
            return {"from": start.isoformat(), "to": end.isoformat()}

        week_start = now.date() - timedelta(days=now.weekday())
        if cls._THIS_WEEK_RE.search(text):
            start = datetime.combine(week_start, time.min, tzinfo=now.tzinfo)
            end = now
            return {"from": start.isoformat(), "to": end.isoformat()}

        if cls._LAST_WEEK_RE.search(text):
            last_week_start = week_start - timedelta(days=7)
            last_week_end = week_start - timedelta(days=1)
            start = datetime.combine(last_week_start, time.min, tzinfo=now.tzinfo)
            end = datetime.combine(last_week_end, time.max, tzinfo=now.tzinfo)
            return {"from": start.isoformat(), "to": end.isoformat()}

        return None

    @staticmethod
    def _load_prompt_spec(path: Path) -> dict:
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        for key in ("system_prompt", "user_template"):
            if key not in payload:
                raise InputExtractionError(f"extractor prompt is missing key {key!r}")
        return payload
