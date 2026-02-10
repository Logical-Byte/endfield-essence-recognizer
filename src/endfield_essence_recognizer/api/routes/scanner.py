from fastapi import APIRouter, Depends

from endfield_essence_recognizer.core.scanner.engine import ScannerEngine
from endfield_essence_recognizer.dependencies import (
    get_scanner_engine_dep,
    get_scanner_service,
)
from endfield_essence_recognizer.services.scanner_service import ScannerService

router = APIRouter(prefix="", tags=["scanner"])


@router.post("/start_scanning")
async def start_scanning(
    scanner: ScannerEngine = Depends(get_scanner_engine_dep),
    scanner_service: ScannerService = Depends(get_scanner_service),
) -> None:
    scanner_service.toggle_scan(scanner_factory=lambda: scanner)
