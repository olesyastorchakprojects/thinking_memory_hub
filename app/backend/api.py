from __future__ import annotations

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.errors import BackendProcessingError, IntentParseError, MemoryServerError
from backend.message_service import MessageService
from backend.models import (
    BackendErrorCode,
    ErrorBody,
    ErrorResponse,
    HealthResponse,
    MessageRequest,
)


def create_api_router(message_service: MessageService) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/health")
    async def get_health() -> dict:
        return HealthResponse.ok().model_dump()

    @router.post("/message", response_model=None)
    async def post_message(payload: dict = Body(...)):
        try:
            request = MessageRequest.model_validate(payload)
        except ValidationError as exc:
            return _error_response(
                BackendErrorCode.invalid_request,
                str(exc),
                status_code=400,
            )

        try:
            response = await message_service.process_message(request)
            return response.model_dump(mode="json")
        except IntentParseError as exc:
            return _error_response(
                BackendErrorCode.intent_parse_failed,
                str(exc),
                status_code=400,
            )
        except MemoryServerError as exc:
            return _error_response(
                BackendErrorCode.memory_server_error,
                str(exc),
                status_code=502,
            )
        except BackendProcessingError as exc:
            return _error_response(
                BackendErrorCode.backend_processing_failed,
                str(exc),
                status_code=500,
            )

    return router


def _error_response(code: BackendErrorCode, message: str, *, status_code: int) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message))
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))
