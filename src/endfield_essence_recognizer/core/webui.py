from endfield_essence_recognizer.core.config import get_server_config
from endfield_essence_recognizer.version import __version__


def get_webview_title() -> str:
    server_config = get_server_config()
    webview_url = server_config.webview_url
    return f"终末地基质妙妙小工具 v{__version__} ({webview_url})"
