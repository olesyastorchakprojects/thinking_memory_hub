from __future__ import annotations

import asyncio
import logging

from memory_server.config import load_settings
from memory_server.server import build_server
from memory_server.storage_client import StorageClient


logger = logging.getLogger(__name__)

async def run() -> None:
    logger.info("Loading server settings")
    settings = load_settings()
    logger.info(
        "Loaded settings host=%s port=%s",
        settings.memory_server_host,
        settings.memory_server_port,
    )

    logger.info("Creating StorageClient")
    storage_client = StorageClient(settings.database_url)
    logger.info("Opening StorageClient pool")
    await storage_client.open()
    logger.info("StorageClient pool opened")

    logger.info("Building FastMCP server")
    mcp = build_server(storage_client)
    mcp.settings.host = settings.memory_server_host
    mcp.settings.port = settings.memory_server_port
    logger.info(
        "Configured FastMCP settings host=%s port=%s transport=%s",
        mcp.settings.host,
        mcp.settings.port,
        "streamable-http",
    )
    try:
        logger.info("Starting FastMCP run_streamable_http_async()")
        await mcp.run_streamable_http_async()
    finally:
        logger.info("Closing StorageClient pool")
        await storage_client.close()
        logger.info("StorageClient pool closed")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()
