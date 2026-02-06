from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

from endfield_essence_recognizer.utils.log import CONSOLE_LOG_FORMAT

if TYPE_CHECKING:
    from endfield_essence_recognizer.core.config import ServerConfig


class LogService:
    """
    Service responsible for broadcasting logs to all connected WebSocket clients.

    The `scope` method manages the lifecycle of the service, and should be called
    in the server's lifespan context to ensure proper setup and teardown.


    """

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._broadcast_task: asyncio.Task[None] | None = None
        self._handler_id: int | None = None

    def log_sink(self, message: str) -> None:
        """
        Loguru-compatible sink that puts log messages into the broadcast queue.
        """
        self._queue.put_nowait(message)

    def add_connection(self, websocket: WebSocket) -> None:
        """
        Register a new WebSocket connection for log broadcasting. This should be called
        when a new client connects to a specific endpoint of the server.
        """
        self._connections.add(websocket)
        logger.debug(f"Log WebSocket connection added. Total: {len(self._connections)}")

    def remove_connection(self, websocket: WebSocket) -> None:
        """
        Unregister a WebSocket connection.
        """
        self._connections.discard(websocket)
        logger.debug(
            f"Log WebSocket connection removed. Total: {len(self._connections)}"
        )

    async def broadcast_loop(self) -> None:
        """
        Background loop that consumes the log queue and broadcasts messages.
        """
        while True:
            try:
                message = await self._queue.get()
                if not self._connections:
                    self._queue.task_done()
                    continue

                disconnected = set()
                for connection in self._connections:
                    try:
                        await connection.send_text(message)
                    except (WebSocketDisconnect, RuntimeError):
                        disconnected.add(connection)
                    except Exception as e:
                        logger.error(f"Error broadcasting log message: {e}")
                        disconnected.add(connection)

                for conn in disconnected:
                    self.remove_connection(conn)

                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in broadcast_loop: {e}")
                await asyncio.sleep(1)

    def start(self) -> None:
        """
        Start the background broadcast loop.
        """
        if self._broadcast_task is None or self._broadcast_task.done():
            self._broadcast_task = asyncio.create_task(self.broadcast_loop())
            logger.info("Log broadcast service started.")

    async def stop(self) -> None:
        """
        Stop the background broadcast loop and clear connections.
        """
        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass
            self._broadcast_task = None

        # Close all active connections
        for connection in list(self._connections):
            try:
                await connection.close()
            except Exception:
                pass
        self._connections.clear()
        logger.info("Log broadcast service stopped.")

    @asynccontextmanager
    async def scope(self, config: ServerConfig):
        """
        Lifecycle manager for LogService.
        Binds to loguru, starts broadcasting, and cleans up.
        """
        # Bind log_sink to loguru
        self._handler_id = logger.add(
            self.log_sink,
            level=str(config.log_level),
            format=CONSOLE_LOG_FORMAT,
            colorize=True,
            diagnose=True,
            filter=lambda record: record["extra"].get("module") != "uvicorn",
        )

        self.start()
        try:
            yield self
        finally:
            if self._handler_id is not None:
                logger.remove(self._handler_id)
                self._handler_id = None
            await self.stop()
