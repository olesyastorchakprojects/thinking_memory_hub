from __future__ import annotations

import json
from pathlib import Path

from backend.errors import IntentParseError
from backend.model_client import ModelClient
from backend.models import (
    IntentClassificationResult,
    ModelGenerationRequest,
    ModelMessage,
    ModelMessageRole,
)


class IntentClassifier:
    def __init__(
        self,
        model_client: ModelClient,
        *,
        prompt_path: Path | None = None,
    ) -> None:
        self._model_client = model_client
        self._prompt_path = prompt_path or (
            Path(__file__).resolve().parents[2]
            / "docs"
            / "specs"
            / "backend_intent_classifier.prompt.json"
        )
        self._prompt_spec = self._load_prompt_spec(self._prompt_path)

    async def classify(
        self, user_message: str, *, trace_id: str | None = None
    ) -> IntentClassificationResult:
        if not user_message.strip():
            raise IntentParseError("user message must be non-empty")

        request = ModelGenerationRequest(
            messages=[
                ModelMessage(
                    role=ModelMessageRole.system,
                    content=self._prompt_spec["system_prompt"],
                ),
                ModelMessage(
                    role=ModelMessageRole.user,
                    content=self._prompt_spec["user_template"].replace(
                        "{{user_message}}", user_message
                    ),
                ),
            ],
            temperature=0.0,
            max_output_tokens=1000,
            response_schema=self._prompt_spec["response_schema"],
        )
        response = await self._model_client.generate(
            request, trace_id=trace_id, span_name="intent_classifier"
        )
        try:
            payload = json.loads(response.content)
        except json.JSONDecodeError as exc:
            raise IntentParseError("classifier returned invalid JSON") from exc

        try:
            return IntentClassificationResult.model_validate(payload)
        except Exception as exc:
            raise IntentParseError("classifier returned invalid intent payload") from exc

    @staticmethod
    def _load_prompt_spec(path: Path) -> dict:
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        for key in ("system_prompt", "user_template", "response_schema"):
            if key not in payload:
                raise IntentParseError(f"intent classifier prompt is missing key {key!r}")
        return payload
