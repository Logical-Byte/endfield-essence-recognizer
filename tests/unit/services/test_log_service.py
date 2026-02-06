import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from loguru import logger

from endfield_essence_recognizer.core.config import ServerConfig
from endfield_essence_recognizer.services.log_service import LogService


@pytest.fixture
def log_service():
    """Fixture providing a fresh LogService instance."""
    return LogService()


@pytest.mark.asyncio
async def test_log_sink_puts_in_queue(log_service: LogService):
    """Test that the log_sink method correctly puts messages into the internal queue."""
    message = "Test log message"
    log_service.log_sink(message)
    assert log_service._queue.qsize() == 1
    assert await log_service._queue.get() == message


@pytest.mark.asyncio
async def test_add_remove_connection(log_service: LogService):
    """Test adding and removing WebSocket connections from the service."""
    mock_ws = MagicMock()
    log_service.add_connection(mock_ws)
    assert mock_ws in log_service._connections

    log_service.remove_connection(mock_ws)
    assert mock_ws not in log_service._connections


@pytest.mark.asyncio
async def test_broadcast_loop_sends_to_websockets(log_service: LogService):
    """Test that the broadcast loop correctly sends messages from the queue to connected WebSockets."""
    mock_ws = AsyncMock()
    # Use an event to notify when send_text is called
    sent_event = asyncio.Event()
    mock_ws.send_text.side_effect = lambda *args, **kwargs: sent_event.set()

    log_service.add_connection(mock_ws)

    # Start broadcast loop in background
    task = asyncio.create_task(log_service.broadcast_loop())

    message = "Broadcast message"
    log_service.log_sink(message)

    # Wait for the event instead of sleeping
    try:
        await asyncio.wait_for(sent_event.wait(), timeout=1.0)
    except asyncio.TimeoutError:
        pytest.fail("Broadcast loop did not send message within timeout")

    mock_ws.send_text.assert_called_with(message)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_scope_context_manager(log_service: LogService):
    """Test the scope context manager for correct initialization and cleanup of handlers and tasks."""
    config = ServerConfig(log_level="DEBUG")
    mock_ws = AsyncMock()
    # Use an event to notify when send_text is called
    sent_event = asyncio.Event()
    mock_ws.send_text.side_effect = lambda *args, **kwargs: sent_event.set()

    log_service.add_connection(mock_ws)

    async with log_service.scope(config):
        assert log_service._broadcast_task is not None
        assert not log_service._broadcast_task.done()
        assert log_service._handler_id is not None

        # Test if it actually captures logs
        test_msg = "Context manager test log"
        logger.info(test_msg)

        # Wait for the event instead of sleeping
        try:
            await asyncio.wait_for(sent_event.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            pytest.fail("Log was not broadcasted via scope within timeout")

        assert mock_ws.send_text.called

    assert log_service._broadcast_task is None
    assert log_service._handler_id is None
