import threading
from unittest.mock import MagicMock

from endfield_essence_recognizer.services.scanner_service import ScannerService


def test_scanner_service_start_scan():
    """
    Test starting the scanner service.

    Verifies that start_scan() correctly spawns a thread and calls execute().
    """
    # Event used to signal that the worker thread has actually started executing
    execute_called = threading.Event()
    # Event used to block the worker thread so we can test the 'is_running' state
    block_execute = threading.Event()

    def mock_execute(stop_event):
        execute_called.set()  # Tell the main test thread we started
        block_execute.wait()  # Wait here until the test tells us to finish

    mock_scanner = MagicMock()
    mock_scanner.execute = mock_execute
    service = ScannerService(scanner_factory=lambda: mock_scanner)

    assert not service.is_running()
    service.start_scan()

    # Wait for the worker thread to reach the execute_called.set() line
    assert execute_called.wait(timeout=1.0)
    assert service.is_running()

    # We must unblock the mock_execute function, otherwise stop_scan()
    # will hang forever while trying to join() the thread.
    block_execute.set()
    service.stop_scan()
    assert not service.is_running()


def test_scanner_service_toggle_scan():
    """
    Test toggling the scanner service.

    Verifies that toggle_scan() switches between running and stopped states.
    """
    execute_called = threading.Event()
    block_execute = threading.Event()

    def mock_execute(stop_event):
        execute_called.set()
        block_execute.wait()

    mock_scanner = MagicMock()
    mock_scanner.execute = mock_execute
    service = ScannerService(scanner_factory=lambda: mock_scanner)

    # First toggle: Start the scan
    service.toggle_scan()
    assert execute_called.wait(timeout=1.0)
    assert service.is_running()

    # Second toggle: Stop the scan
    # We unblock the worker so the join() inside toggle_scan can complete
    block_execute.set()
    service.toggle_scan()
    assert not service.is_running()
    assert service._stop_event.is_set()


def test_scanner_service_already_running():
    """
    Test starting the scanner service when it's already active.

    Verifies that multiple calls to start_scan() do not spawn multiple threads.
    """
    execute_event = threading.Event()
    block_event = threading.Event()

    mock_scanner = MagicMock()

    def side_effect(stop_event):
        execute_event.set()
        block_event.wait()

    mock_scanner.execute.side_effect = side_effect

    service = ScannerService(scanner_factory=lambda: mock_scanner)

    # Start the first time
    service.start_scan()
    assert execute_event.wait(timeout=1.0)

    # Calling it again while the first one is blocked should do nothing
    service.start_scan()

    # Verify that mock_scanner.execute was only called once
    assert mock_scanner.execute.call_count == 1

    # Cleanup
    block_event.set()
    service.stop_scan()
