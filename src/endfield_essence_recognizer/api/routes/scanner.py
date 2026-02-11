from fastapi import APIRouter, Depends
from pydantic import BaseModel

from endfield_essence_recognizer.core.interfaces import AutomationEngine
from endfield_essence_recognizer.core.scanner.engine import (
    OneTimeRecognitionEngine,
    ScannerEngine,
)
from endfield_essence_recognizer.dependencies import (
    get_delivery_claimer_engine_dep,
    get_one_time_recognition_engine_dep,
    get_scanner_engine_dep,
    get_scanner_service,
    require_game_or_webview_is_active,
    require_game_window_exists,
)
from endfield_essence_recognizer.schemas.scanner import TaskType
from endfield_essence_recognizer.services.scanner_service import ScannerService

router = APIRouter(prefix="", tags=["scanner"])


class ToggleScanningRequest(BaseModel):
    task_type: TaskType


@router.post(
    "/recognize_once",
    dependencies=[
        Depends(require_game_or_webview_is_active),
        Depends(require_game_window_exists),
    ],
)
async def recognize_once(
    engine: OneTimeRecognitionEngine = Depends(get_one_time_recognition_engine_dep),
    scanner_service: ScannerService = Depends(get_scanner_service),
) -> None:
    scanner_service.start_scan(scanner_factory=lambda: engine)


@router.post(
    "/start_scanning",
    dependencies=[
        Depends(require_game_or_webview_is_active),
        Depends(require_game_window_exists),
    ],
)
async def start_scanning(
    scanner: ScannerEngine = Depends(get_scanner_engine_dep),
    scanner_service: ScannerService = Depends(get_scanner_service),
) -> None:
    scanner_service.toggle_scan(scanner_factory=lambda: scanner)


@router.post(
    "/toggle_scanning",
    dependencies=[
        Depends(require_game_or_webview_is_active),
        Depends(require_game_window_exists),
    ],
)
async def toggle_scanning(
    request: ToggleScanningRequest,
    scanner_service: ScannerService = Depends(get_scanner_service),
    essence_engine: ScannerEngine = Depends(get_scanner_engine_dep),
    delivery_engine: AutomationEngine = Depends(get_delivery_claimer_engine_dep),
) -> None:
    def get_engine() -> AutomationEngine:
        match request.task_type:
            case TaskType.ESSENCE:
                return essence_engine
            case TaskType.DELIVERY_CLAIM:
                return delivery_engine
            case _:
                raise ValueError(f"Unsupported task type: {request.task_type}")

    scanner_service.toggle_scan(scanner_factory=get_engine)
