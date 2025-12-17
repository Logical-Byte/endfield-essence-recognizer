from __future__ import annotations

import sys

from loguru import logger

# default_format: str = (
#     '<dim>File <cyan>"{file.path}"</>, line <cyan>{line}</>, in <cyan>{function}</></>\n'
#     "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</> "
#     "[<level>{level}</>] "
#     "<level><normal>{message}</></>"
# )

# default_format: str = (
#     "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</> "
#     "[<level>{level}</>] "
#     "<cyan>{module}</>:<cyan>{function}</>:<cyan>{line}</> | "
#     "<level><normal>{message}</></>"
# )

default_format: str = (
    "<green>{time:MM-DD HH:mm:ss}</> [<level>{level}</>] <level><normal>{message}</></>"
)

logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    format=default_format,
    diagnose=True,
)
