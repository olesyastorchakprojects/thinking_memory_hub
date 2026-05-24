from __future__ import annotations

from fastapi import FastAPI

from backend.api import create_api_router
from backend.message_service import MessageService
from backend.slack import SlackEventHandler, create_slack_router


def build_app(
    message_service: MessageService,
    *,
    slack_event_handler: SlackEventHandler | None = None,
) -> FastAPI:
    app = FastAPI(title="thinking-memory-backend")
    app.include_router(create_api_router(message_service))
    if slack_event_handler is not None:
        app.include_router(create_slack_router(slack_event_handler))
    return app
