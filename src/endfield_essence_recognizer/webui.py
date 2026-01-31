from typing import cast

import webview

from endfield_essence_recognizer.server import is_dev, webview_url
from endfield_essence_recognizer.utils.log import logger
from endfield_essence_recognizer.version import __version__

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
