from __future__ import annotations

import asyncio

import uvicorn

from backend.config import load_settings
from backend.input_extractor import StructuredInputExtractor
from backend.intent_classifier import IntentClassifier
from backend.memory_client import MemoryClient
from backend.message_service import MessageService
from backend.model_client import ModelClient
from backend.server import build_app
from backend.slack import SlackClient, SlackEventHandler, SlackSignatureVerifier


async def run() -> None:
    settings = load_settings()
    memory_client = MemoryClient(settings.memory_server_url)
    model_client = ModelClient(
        base_url=settings.together_url,
        api_key=settings.together_api_key,
        model_name=settings.together_model,
    )
    slack_client: SlackClient | None = None
    try:
        await memory_client.open()
        message_service = MessageService(
            memory_client=memory_client,
            intent_classifier=IntentClassifier(model_client),
            input_extractor=StructuredInputExtractor(model_client),
        )
        slack_event_handler = None
        if settings.slack_signing_secret and settings.slack_bot_token:
            slack_client = SlackClient(
                bot_token=settings.slack_bot_token,
                api_base_url=settings.slack_api_base_url,
            )
            slack_event_handler = SlackEventHandler(
                message_service=message_service,
                slack_client=slack_client,
                signature_verifier=SlackSignatureVerifier(settings.slack_signing_secret),
            )
        app = build_app(message_service, slack_event_handler=slack_event_handler)
        config = uvicorn.Config(
            app,
            host=settings.backend_host,
            port=settings.backend_port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()
    finally:
        await memory_client.close()
        await model_client.close()
        if slack_client is not None:
            await slack_client.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
