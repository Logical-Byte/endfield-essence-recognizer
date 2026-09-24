"""结构化事件推送服务：向后端后台任务结束后需要刷新的前端页面广播事件。"""

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

#: 扫描结果已同步到 profiles（宝藏基质配置变更），前端应刷新相关页面数据。
EVENT_PROFILES_CHANGED = "profiles_changed"


class EventService:
    """事件广播服务。

    后台任务（如扫描线程）通过 publish 发布事件，服务将事件以 JSON 形式
    广播给所有已连接的 WebSocket 客户端。publish 可在任意线程调用
    （通过 asyncio.Queue 传递给事件循环中的广播任务）。
    """

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._broadcast_task: asyncio.Task[None] | None = None

    def publish(self, event: dict[str, Any]) -> None:
        """发布一个事件，广播给所有连接（可在任意线程调用）。"""
        self._queue.put_nowait(event)

    async def add_connection(self, websocket: WebSocket) -> None:
        """注册新的 WebSocket 连接。"""
        self._connections.add(websocket)
        logger.debug(
            f"Event WebSocket connection added. Total: {len(self._connections)}"
        )

    def remove_connection(self, websocket: WebSocket) -> None:
        """注销 WebSocket 连接。"""
        self._connections.discard(websocket)
        logger.debug(
            f"Event WebSocket connection removed. Total: {len(self._connections)}"
        )

    async def broadcast_loop(self) -> None:
        """后台循环：消费事件队列并向所有连接广播。"""
        while True:
            try:
                event = await self._queue.get()

                if not self._connections:
                    continue

                disconnected: set[WebSocket] = set()
                for connection in self._connections:
                    try:
                        await connection.send_json(event)
                    except (WebSocketDisconnect, RuntimeError):
                        disconnected.add(connection)
                    except Exception as exc:
                        logger.error(f"Error broadcasting event: {exc}")
                        disconnected.add(connection)

                for connection in disconnected:
                    self.remove_connection(connection)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Unexpected error in event broadcast loop: {exc}")
                await asyncio.sleep(1)

    def start(self) -> None:
        """启动后台广播任务。"""
        if self._broadcast_task is None or self._broadcast_task.done():
            self._broadcast_task = asyncio.create_task(self.broadcast_loop())
            logger.debug("Event broadcast service started.")

    async def stop(self) -> None:
        """停止广播任务并关闭所有连接。"""
        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass
            self._broadcast_task = None

        for connection in list(self._connections):
            try:
                await connection.close()
            except Exception as exc:
                logger.warning(f"Error while closing event connection: {exc}")
        self._connections.clear()
        logger.debug("Event broadcast service stopped.")

    @asynccontextmanager
    async def scope(self):
        """服务生命周期管理：启动广播循环，退出时清理。"""
        self.start()
        try:
            yield self
        finally:
            await self.stop()
