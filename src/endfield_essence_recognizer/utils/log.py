"""
Logging utilities of the server process.

Provides loguru logger configuration and a WebSocket log handler.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import sys

from loguru import logger

from endfield_essence_recognizer.core.path import get_logs_dir

file_log_format = (
    '<dim>File <cyan>"{file.path}"</>, line <cyan>{line}</>, in <cyan>{function}</></>\n'
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</> "
    "[<level>{level}</>] "
    "<level><normal>{message}</></>"
)

# default_format = (
#     "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</> "
#     "[<level>{level}</>] "
#     "<cyan>{module}</>:<cyan>{function}</>:<cyan>{line}</> | "
#     "<level><normal>{message}</></>"
# )

console_log_format = (
    "<green>{time:MM-DD HH:mm:ss}</> [<level>{level}</>] <level><normal>{message}</></>"
)

gui_log_format = file_log_format


# https://loguru.readthedocs.io/en/stable/overview.html#entirely-compatible-with-standard-logging
class LoguruHandler(logging.Handler):
    """logging 与 loguru 之间的桥梁，将 logging 的日志转发到 loguru。"""

    def emit(self, record: logging.LogRecord):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        message = f"<magenta>{record.name.split('.')[0]}</> | {record.getMessage()}"
        logger.opt(colors=True, depth=depth, exception=record.exc_info).bind(
            module="uvicorn"
        ).log(level, message)


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "default": {"class": "endfield_essence_recognizer.utils.log.LoguruHandler"}
    },
    "loggers": {
        "uvicorn.error": {"handlers": ["default"], "level": "INFO"},
        "uvicorn.access": {"handlers": ["default"], "level": "INFO"},
    },
}


class WebSocketHandler:
    """将日志发送到 WebSocket 连接的处理器"""

    def __init__(self):
        self.log_queue: asyncio.Queue[str] = asyncio.Queue()

    def write(self, message: str):
        self.log_queue.put_nowait(message)


websocket_handler = WebSocketHandler()


logger.remove()
if sys.stderr:  # 打包后可能没有 stderr
    logger.add(
        sys.stderr,
        level="INFO",
        format=console_log_format,
        diagnose=True,
    )
logger.add(
    get_logs_dir() / "log_{time:YYYY-MM-DD}.log",
    level="TRACE",
    format=file_log_format,
    diagnose=True,
)
logger.add(
    websocket_handler,
    level="INFO",
    format=console_log_format,
    colorize=True,
    diagnose=True,
    filter=lambda record: record["extra"].get("module") != "uvicorn",
)
