import webview

from endfield_essence_recognizer.log import logger
from endfield_essence_recognizer.server import webview_url

window = webview.create_window(
    title=f"终末地基质妙妙小工具 ({webview_url})",
    url=webview_url,
    width=1600,
    height=900,
    resizable=True,
)


def start_pywebview():
    logger.info("正在启动 UI 界面...")
    webview.start()
