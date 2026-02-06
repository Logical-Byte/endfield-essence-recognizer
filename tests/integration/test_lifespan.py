import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from loguru import logger

from endfield_essence_recognizer.deps import get_log_service
from endfield_essence_recognizer.server import app


@pytest.mark.asyncio
async def test_lifespan_integration_log_service():
    """
    Integration test for the FastAPI lifespan.
    Verifies that LogService is correctly initialized and cleaned up.
    """
    log_service = get_log_service()

    # We patch keyboard to avoid side effects on the host OS during integration tests
    with patch("endfield_essence_recognizer.server.keyboard") as mock_keyboard:
        # Use FastAPI's lifespan context directly to ensure it runs
        async with app.router.lifespan_context(app):
            # --- Startup phase complete (yield reached) ---

            # Verify LogService state
            assert log_service._broadcast_task is not None
            assert not log_service._broadcast_task.done()
            assert log_service._handler_id is not None

            # Verify hotkeys were registered
            assert mock_keyboard.add_hotkey.called

            # Verify log capture works by adding a mock connection
            mock_ws = AsyncMock()
            await log_service.add_connection(mock_ws)

            logger.info("Integration test log message")

            # Wait for the broadcast loop to process the message
            await asyncio.sleep(log_service.batch_timeout + 0.05)
            assert mock_ws.send_text.called

            log_service.remove_connection(mock_ws)

        # --- Shutdown phase complete ---

        # Verify cleanup
        assert log_service._broadcast_task is None
        assert log_service._handler_id is None
        assert len(log_service._connections) == 0

        # Verify hotkeys were unhooked
        mock_keyboard.unhook_all.assert_called_once()
