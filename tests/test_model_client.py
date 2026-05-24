from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.errors import ModelClientError
from backend.model_client import ModelClient
from backend.models import (
    ModelGenerationRequest,
    ModelMessage,
    ModelMessageRole,
)


def _request() -> ModelGenerationRequest:
    return ModelGenerationRequest(
        messages=[ModelMessage(role=ModelMessageRole.user, content="hello")],
        temperature=0.0,
        max_output_tokens=128,
        response_schema={
            "type": "object",
            "additionalProperties": False,
            "required": ["intent"],
            "properties": {"intent": {"type": "string"}},
        },
    )


def test_model_client_validates_constructor():
    with pytest.raises(ModelClientError):
        ModelClient(base_url="postgres://bad", api_key="x", model_name="m")


@pytest.mark.asyncio
async def test_model_client_builds_json_schema_request():
    client = ModelClient(
        base_url="https://api.together.xyz",
        api_key="key",
        model_name="model",
    )
    post = AsyncMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "choices": [{"message": {"content": "{\"intent\":\"save_note\",\"reason\":\"default\",\"confidence\":\"high\"}"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
    }
    post.return_value = response
    client._http_client.post = post  # type: ignore[method-assign]

    await client.generate(_request())

    sent = post.await_args.kwargs["json"]
    assert sent["response_format"]["type"] == "json_schema"
    assert "schema" in sent["response_format"]["json_schema"]
    await client.close()


@pytest.mark.asyncio
async def test_model_client_maps_bad_status_to_error():
    client = ModelClient(
        base_url="https://api.together.xyz",
        api_key="key",
        model_name="model",
    )
    post = AsyncMock()
    response = MagicMock()
    response.status_code = 500
    post.return_value = response
    client._http_client.post = post  # type: ignore[method-assign]

    with pytest.raises(ModelClientError):
        await client.generate(_request())
    await client.close()


@pytest.mark.asyncio
async def test_model_client_rejects_empty_content():
    client = ModelClient(
        base_url="https://api.together.xyz",
        api_key="key",
        model_name="model",
    )
    post = AsyncMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "choices": [{"message": {"content": ""}, "finish_reason": "stop"}],
        "usage": {},
    }
    post.return_value = response
    client._http_client.post = post  # type: ignore[method-assign]

    with pytest.raises(ModelClientError):
        await client.generate(_request())
    await client.close()
