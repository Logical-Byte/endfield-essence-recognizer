import importlib.resources

import uvicorn
from fastapi import (
    FastAPI,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from endfield_essence_recognizer.api.lifespan import lifespan
from endfield_essence_recognizer.api.router import api_router, ws_router
from endfield_essence_recognizer.core.config import ServerConfig, get_server_config
from endfield_essence_recognizer.exceptions import (
    UnsupportedResolutionError,
    WindowNotFoundError,
)
from endfield_essence_recognizer.utils.log import (
    LOGGING_CONFIG,
)

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,  # type: ignore[invalid-argument-type]
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(WindowNotFoundError)
async def window_not_found_exception_handler(
    _request: Request, exc: WindowNotFoundError
):
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )


@app.exception_handler(UnsupportedResolutionError)
async def unsupported_resolution_exception_handler(
    _request: Request, exc: UnsupportedResolutionError
):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )


# Include routers
app.include_router(api_router)
app.include_router(ws_router)

# Mount game data static files
app.mount(
    "/api/data",
    StaticFiles(
        directory=str(importlib.resources.files("endfield_essence_recognizer") / "data")
    ),
    name="data",
)


def get_server() -> uvicorn.Server:
    cfg: ServerConfig = get_server_config()
    api_host = cfg.api_host
    api_port = cfg.api_port
    config = uvicorn.Config(
        app=app,
        host=api_host,
        port=api_port,
        log_config=LOGGING_CONFIG,
    )
    server = uvicorn.Server(config)
    return server
