from __future__ import annotations

import json
from typing import Any

import httpx
from langfuse import Langfuse

from backend.errors import ModelClientError
from backend.models import ModelGenerationRequest, ModelGenerationResponse

# together.ai pricing (USD per 1M tokens)
_INPUT_PRICE_PER_1M: float = 0.05
_OUTPUT_PRICE_PER_1M: float = 0.20

_langfuse = Langfuse()


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
        *,
        trace_id: str | None = None,
        span_name: str = "llm_generate",
    ) -> ModelGenerationResponse:
        trace = _langfuse.trace(id=trace_id) if trace_id else _langfuse.trace(name=span_name)
        generation = trace.generation(
            name=span_name,
            model=self._model_name,
            input=[m.model_dump() for m in request.messages],
        )

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
            generation.end(level="ERROR", status_message=str(exc))
            raise ModelClientError("model transport failure") from exc

        if response.status_code < 200 or response.status_code >= 300:
            generation.end(level="ERROR", status_message=f"HTTP {response.status_code}")
            raise ModelClientError(f"unexpected HTTP status: {response.status_code}")

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            generation.end(level="ERROR", status_message="invalid JSON")
            raise ModelClientError("invalid response JSON") from exc

        try:
            choice = payload["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            generation.end(level="ERROR", status_message="invalid response shape")
            raise ModelClientError("invalid response shape") from exc

        if not isinstance(content, str) or not content.strip():
            generation.end(level="ERROR", status_message="empty content")
            raise ModelClientError("model returned empty content")

        usage = payload.get("usage") or {}
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        input_cost = (
            prompt_tokens * _INPUT_PRICE_PER_1M / 1_000_000
            if prompt_tokens is not None
            else None
        )
        output_cost = (
            completion_tokens * _OUTPUT_PRICE_PER_1M / 1_000_000
            if completion_tokens is not None
            else None
        )

        generation.end(
            output=content,
            usage={
                "input": prompt_tokens,
                "output": completion_tokens,
                "input_cost": input_cost,
                "output_cost": output_cost,
            },
        )

        return ModelGenerationResponse(
            content=content,
            finish_reason=choice.get("finish_reason"),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=usage.get("total_tokens"),
            input_cost=input_cost,
            output_cost=output_cost,
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
