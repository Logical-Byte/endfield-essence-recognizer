import asyncio
from unittest.mock import AsyncMock

import pytest
from loguru import logger

from endfield_essence_recognizer.core.config import ServerConfig
from endfield_essence_recognizer.services.log_service import LogService, _collect_batch


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
    mock_ws = AsyncMock()
    await log_service.add_connection(mock_ws)
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

    await log_service.add_connection(mock_ws)

    # Start broadcast loop in background
    task = asyncio.create_task(log_service.broadcast_loop())

    message = "Broadcast message"
    log_service.log_sink(message)

    # Wait for the event instead of sleeping
    try:
        await asyncio.wait_for(sent_event.wait(), timeout=1.0)
    except TimeoutError:
        pytest.fail("Broadcast loop did not send message within timeout")

    mock_ws.send_text.assert_called_with(message)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_broadcast_multiple_messages(log_service: LogService):
    """Test that the broadcast loop correctly sends multiple messages in sequence."""
    mock_ws = AsyncMock()
    received_messages = []

    test_messages = [f"Message {i}" for i in range(5)]

    # Event to trigger when we found all messages
    all_found_event = asyncio.Event()

    async def mock_send_text(msg):
        received_messages.append(msg)
        # Check if we have found all test messages in the received data
        count = sum(1 for m in test_messages if any(m in r for r in received_messages))
        if count == len(test_messages):
            all_found_event.set()

    mock_ws.send_text.side_effect = mock_send_text
    await log_service.add_connection(mock_ws)

    # Start broadcast loop
    task = asyncio.create_task(log_service.broadcast_loop())

    # Send messages
    for msg in test_messages:
        log_service.log_sink(msg)

    try:
        await asyncio.wait_for(all_found_event.wait(), timeout=2.0)
    except TimeoutError:
        pytest.fail(f"Did not receive all messages. Received: {received_messages}")

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_collect_batch_immediate_full():
    """Test _collect_batch returns immediately when enough items are available."""
    queue = asyncio.Queue()
    for i in range(5):
        queue.put_nowait(f"msg{i}")

    batch = await _collect_batch(queue, max_batch_size=3, max_timeout=1.0)

    assert len(batch) == 3
    assert batch == ["msg0", "msg1", "msg2"]
    assert queue.qsize() == 2


@pytest.mark.asyncio
async def test_collect_batch_timeout_partial():
    """Test _collect_batch returns partial batch after timeout."""
    queue = asyncio.Queue()
    queue.put_nowait("msg0")
    queue.put_nowait("msg1")

    # We ask for 5 items, but only 2 are available.
    # The function should collect the 2, then wait for timeout.

    batch = await _collect_batch(queue, max_batch_size=5, max_timeout=0.1)

    assert len(batch) == 2
    assert batch == ["msg0", "msg1"]
    assert queue.empty()


@pytest.mark.asyncio
async def test_collect_batch_single_item():
    """Test _collect_batch respects max_batch_size=1."""
    queue = asyncio.Queue()
    queue.put_nowait("msg0")
    queue.put_nowait("msg1")

    batch = await _collect_batch(queue, max_batch_size=1, max_timeout=1.0)

    assert len(batch) == 1
    assert batch == ["msg0"]
    assert queue.qsize() == 1


@pytest.mark.asyncio
async def test_collect_batch_waits_for_first_item():
    """Test _collect_batch blocks strictly for the first item."""
    queue = asyncio.Queue()

    task = asyncio.create_task(_collect_batch(queue, max_batch_size=3, max_timeout=0.1))

    # Quick sleep to ensure task is running and waiting
    await asyncio.sleep(0.05)
    assert not task.done()

    queue.put_nowait("msg0")

    # It should finish successfully after receiving msg0, then waiting timeout for more
    batch = await task
    assert batch == ["msg0"]


@pytest.mark.asyncio
async def test_collect_batch_accumulates_slowly():
    """Test _collect_batch accumulates items that arrive within the timeout window."""
    queue = asyncio.Queue()
    queue.put_nowait("msg0")

    task = asyncio.create_task(_collect_batch(queue, max_batch_size=3, max_timeout=0.2))

    await asyncio.sleep(0.05)
    queue.put_nowait("msg1")

    await asyncio.sleep(0.05)
    queue.put_nowait("msg2")

    # By now (approx 0.1s elapsed), we hit max_batch_size=3, so it should return before timeout (0.2s)
    batch = await task
    assert batch == ["msg0", "msg1", "msg2"]


@pytest.mark.asyncio
async def test_collect_batch_timeout_before_second_msg():
    """Test _collect_batch returns partial batch if next message arrives too late."""
    queue = asyncio.Queue()
    queue.put_nowait("msg0")

    # Set timeout to 0.05s, request batch size 2
    task = asyncio.create_task(
        _collect_batch(queue, max_batch_size=2, max_timeout=0.05)
    )

    # Wait longer than timeout (0.05s)
    await asyncio.sleep(0.1)
    queue.put_nowait("msg1")

    # Task should have finished by now with only the first message
    assert task.done()
    batch = await task
    assert batch == ["msg0"]

    # msg1 should still be in the queue
    assert queue.qsize() == 1
    assert await queue.get() == "msg1"


@pytest.mark.asyncio
async def test_scope_context_manager(log_service: LogService):
    """Test the scope context manager for correct initialization and cleanup of handlers and tasks."""
    config = ServerConfig(log_level="DEBUG")
    mock_ws = AsyncMock()
    # Use an event to notify when send_text is called
    sent_event = asyncio.Event()
    mock_ws.send_text.side_effect = lambda *args, **kwargs: sent_event.set()

    await log_service.add_connection(mock_ws)

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
        except TimeoutError:
            pytest.fail("Log was not broadcasted via scope within timeout")

        assert mock_ws.send_text.called

    assert log_service._broadcast_task is None
    assert log_service._handler_id is None


@pytest.mark.asyncio
async def test_log_history_replay(log_service: LogService):
    """Test that connections receive existing history upon joining."""
    messages = ["Log 1\n", "Log 2\n", "Log 3\n"]

    # 1. Fill history without any connections
    # We need to run broadcast_loop to move items from queue to history
    task = asyncio.create_task(log_service.broadcast_loop())

    for msg in messages:
        log_service.log_sink(msg)

    # Wait for processing
    await asyncio.sleep(0.1)

    # 2. Add a new connection and verify history is replayed
    mock_ws = AsyncMock()
    await log_service.add_connection(mock_ws)

    # Verify send_text was called with combined history
    mock_ws.send_text.assert_called_with("".join(messages))

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_log_history_size_limit():
    """Test that history size is correctly capped."""
    history_size = 5
    log_service = LogService(history_size=history_size)

    task = asyncio.create_task(log_service.broadcast_loop())

    # Send more than history_size messages
    for i in range(10):
        log_service.log_sink(f"msg{i}")

    await asyncio.sleep(0.1)

    assert len(log_service._history) == history_size
    # Should contain the LAST 5 messages
    assert list(log_service._history) == [f"msg{i}" for i in range(5, 10)]

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
