from fastapi import APIRouter

from .routes import (
    config,
    matrix_export,
    profiles,
    scanner,
    screenshot,
    static_data,
    system,
    update,
)
from .websockets import events, logs, update_progress

api_router = APIRouter(prefix="/api")
api_router.include_router(config.router)
api_router.include_router(matrix_export.router)
api_router.include_router(profiles.router)
api_router.include_router(scanner.router)
api_router.include_router(screenshot.router)
api_router.include_router(static_data.router)
api_router.include_router(system.router)
api_router.include_router(update.router)

ws_router = APIRouter(prefix="/ws")
ws_router.include_router(events.router)
ws_router.include_router(logs.router)
ws_router.include_router(update_progress.router)
