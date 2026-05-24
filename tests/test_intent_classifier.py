from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from backend.errors import IntentParseError
from backend.intent_classifier import IntentClassifier
from backend.models import IntentClassificationResult


def _prompt_file(tmp_path: Path) -> Path:
    path = tmp_path / "prompt.json"
    path.write_text(
        json.dumps(
            {
                "system_prompt": "system",
                "user_template": "User message:\n{{user_message}}",
                "response_schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["intent", "reason", "confidence"],
                    "properties": {
                        "intent": {
                            "type": "string",
                            "enum": [
                                "save_note",
                                "search_notes",
                                "search_tags",
                                "update_note",
                            ],
                        },
                        "reason": {"type": "string"},
                        "confidence": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                        },
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.mark.asyncio
async def test_classifier_returns_structured_result(tmp_path: Path):
    model_client = AsyncMock()
    model_client.generate.return_value.content = json.dumps(
        {
            "intent": "save_note",
            "reason": "The message is a standalone thought.",
            "confidence": "high",
        }
    )

    classifier = IntentClassifier(model_client, prompt_path=_prompt_file(tmp_path))
    result = await classifier.classify("чем отличаются промпты от ресурсов")

    assert isinstance(result, IntentClassificationResult)
    assert result.intent.value == "save_note"
    assert result.confidence.value == "high"


@pytest.mark.asyncio
async def test_classifier_builds_prompt_request(tmp_path: Path):
    model_client = AsyncMock()
    model_client.generate.return_value.content = json.dumps(
        {
            "intent": "search_notes",
            "reason": "The message asks to view previous notes.",
            "confidence": "medium",
        }
    )

    classifier = IntentClassifier(model_client, prompt_path=_prompt_file(tmp_path))
    await classifier.classify("покажи мои заметки")

    request = model_client.generate.await_args.args[0]
    assert request.messages[0].content == "system"
    assert "покажи мои заметки" in request.messages[1].content
    assert request.response_schema["required"] == ["intent", "reason", "confidence"]


@pytest.mark.asyncio
async def test_classifier_rejects_invalid_json(tmp_path: Path):
    model_client = AsyncMock()
    model_client.generate.return_value.content = "not json"

    classifier = IntentClassifier(model_client, prompt_path=_prompt_file(tmp_path))

    with pytest.raises(IntentParseError):
        await classifier.classify("hello")


@pytest.mark.asyncio
async def test_classifier_rejects_invalid_payload(tmp_path: Path):
    model_client = AsyncMock()
    model_client.generate.return_value.content = json.dumps(
        {"intent": "unknown", "reason": "x", "confidence": "high"}
    )

    classifier = IntentClassifier(model_client, prompt_path=_prompt_file(tmp_path))

    with pytest.raises(IntentParseError):
        await classifier.classify("hello")


def test_classifier_prompt_loader_requires_keys(tmp_path: Path):
    path = tmp_path / "bad_prompt.json"
    path.write_text(json.dumps({"system_prompt": "x"}), encoding="utf-8")

    with pytest.raises(IntentParseError):
        IntentClassifier._load_prompt_spec(path)
