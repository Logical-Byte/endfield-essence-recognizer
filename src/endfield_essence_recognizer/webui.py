from typing import cast

import webview

from endfield_essence_recognizer.core.config import get_server_config
from endfield_essence_recognizer.utils.log import logger
from endfield_essence_recognizer.version import __version__

server_config = get_server_config()
is_dev = server_config.dev_mode
webview_url = server_config.webview_url

window = cast(
    "webview.Window",
    webview.create_window(
        title=f"终末地基质妙妙小工具 v{__version__} ({webview_url})",
        url=webview_url,
        width=1600,
        height=900,
        resizable=True,
    ),
)


def start_pywebview():
    logger.info("正在启动 UI 界面...")
    webview.start(debug=is_dev)
