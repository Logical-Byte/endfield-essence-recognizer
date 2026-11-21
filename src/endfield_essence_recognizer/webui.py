from typing import cast

import webview

from endfield_essence_recognizer.core.config import get_server_config
from endfield_essence_recognizer.core.webui import get_webview_title, read_window_size
from endfield_essence_recognizer.utils.log import logger

server_config = get_server_config()
is_dev = server_config.dev_mode
webview_url = server_config.webview_url

window_width, window_height = read_window_size()

window = cast(
    "webview.Window",
    webview.create_window(
        title=get_webview_title(),
        url=webview_url,
        width=window_width,
        height=window_height,
        resizable=True,
    ),
)


def _on_window_closing() -> None:
    """窗口关闭前记录当前尺寸，供「记住上次关闭时的大小」模式下次启动时恢复。

    走 `UserSettingManager` 而不是自己读写 `config.json`：配置文件只由它一个
    写者负责，否则窗口关闭的写回会和设置保存互相覆盖。
    """
    from endfield_essence_recognizer.dependencies import default_user_setting_manager

    default_user_setting_manager().remember_window_size(window.width, window.height)


window.events.closing += _on_window_closing


def start_pywebview():
    logger.info("正在启动 UI 界面...")
    webview.start(debug=is_dev)
