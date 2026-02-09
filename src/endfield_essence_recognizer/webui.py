from typing import cast

import webview

from endfield_essence_recognizer.core.config import ServerConfig, get_server_config
from endfield_essence_recognizer.core.webui import get_webview_title
from endfield_essence_recognizer.utils.log import logger

server_config: ServerConfig = get_server_config()

window = cast(
    "webview.Window",
    webview.create_window(
        title=get_webview_title(),
        url=server_config.webview_url,
        width=1600,
        height=900,
        resizable=True,
    ),
)


def start_pywebview():
    logger.info("正在启动 UI 界面...")
    webview.start(debug=server_config.webview_debug, gui=server_config.webview_gui)
