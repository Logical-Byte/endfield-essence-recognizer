"""EventService 单元测试。"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from endfield_essence_recognizer.services.event_service import (
    EVENT_PROFILES_CHANGED,
    EventService,
)


@pytest.mark.asyncio
async def test_publish_broadcasts_to_connected_websockets():
    """发布事件后，所有已连接客户端收到 JSON 事件。"""
    service = EventService()
    service.start()
    try:
        mock_ws = AsyncMock()
        await service.add_connection(mock_ws)

        event = {"type": EVENT_PROFILES_CHANGED}
        service.publish(event)
        await asyncio.sleep(0.05)

        mock_ws.send_json.assert_awaited_once_with(event)
        service.remove_connection(mock_ws)
    finally:
        await service.stop()


@pytest.mark.asyncio
async def test_publish_without_connections_does_not_raise():
    """无客户端连接时发布事件不报错。"""
    service = EventService()
    service.start()
    try:
        service.publish({"type": EVENT_PROFILES_CHANGED})
        await asyncio.sleep(0.05)
    finally:
        await service.stop()


@pytest.mark.asyncio
async def test_broadcast_removes_disconnected_websocket():
    """发送失败的客户端会被移出连接集合，不影响其他客户端。"""
    service = EventService()
    service.start()
    try:
        broken_ws = AsyncMock()
        broken_ws.send_json.side_effect = Exception("connection lost")
        healthy_ws = AsyncMock()
        await service.add_connection(broken_ws)
        await service.add_connection(healthy_ws)

        service.publish({"type": EVENT_PROFILES_CHANGED})
        await asyncio.sleep(0.05)

        assert len(service._connections) == 1
        assert healthy_ws in service._connections
        healthy_ws.send_json.assert_awaited_once()
        service.remove_connection(healthy_ws)
    finally:
        await service.stop()
