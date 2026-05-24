from __future__ import annotations

import json
from typing import Any

import httpx

from backend.errors import ModelClientError
from backend.models import ModelGenerationRequest, ModelGenerationResponse


class ModelClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model_name: str,
        timeout_sec: int = 30,
    ) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ModelClientError("base_url must be an HTTP URL")
        if not api_key.strip():
            raise ModelClientError("api_key must be non-empty")
        if not model_name.strip():
            raise ModelClientError("model_name must be non-empty")
        if timeout_sec <= 0:
            raise ModelClientError("timeout_sec must be > 0")

        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model_name = model_name
        self._timeout_sec = timeout_sec
        self._http_client = httpx.AsyncClient(timeout=timeout_sec)

    async def close(self) -> None:
        await self._http_client.aclose()

    async def generate(
        self,
        request: ModelGenerationRequest,
    ) -> ModelGenerationResponse:
        wire_request = self._build_wire_request(request)
        try:
            response = await self._http_client.post(
                f"{self._base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=wire_request,
            )
        except Exception as exc:
            raise ModelClientError("model transport failure") from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise ModelClientError(f"unexpected HTTP status: {response.status_code}")

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise ModelClientError("invalid response JSON") from exc

        try:
            choice = payload["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelClientError("invalid response shape") from exc

        if not isinstance(content, str) or not content.strip():
            raise ModelClientError("model returned empty content")

        usage = payload.get("usage") or {}
        return ModelGenerationResponse(
            content=content,
            finish_reason=choice.get("finish_reason"),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
        )

    def _build_wire_request(self, request: ModelGenerationRequest) -> dict[str, Any]:
        return {
            "model": self._model_name,
            "messages": [
                {"role": message.role.value, "content": message.content}
                for message in request.messages
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "intent_classifier_response",
                    "schema": request.response_schema,
                },
            },
        }
