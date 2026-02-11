from fastapi import APIRouter

from .routes import config, scanner, screenshot, static_data, system
from .websockets import logs

api_router = APIRouter(prefix="/api")
api_router.include_router(config.router)
api_router.include_router(scanner.router)
api_router.include_router(screenshot.router)
api_router.include_router(static_data.router)
api_router.include_router(system.router)

ws_router = APIRouter(prefix="/ws")
ws_router.include_router(logs.router)
