import httpx

from endfield_essence_recognizer.core.config import get_server_config
from endfield_essence_recognizer.utils.log import logger


class HotkeyClient:
    """A minimal HTTP client for sending commands to the local FastAPI server."""

    def __init__(self):
        config = get_server_config()
        self.base_url = f"http://{config.api_host}:{config.api_port}/api"
        self.client = httpx.Client(timeout=5.0)

    def post(self, endpoint: str, json: dict | None = None):
        """Send a POST request to the backend."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            response = self.client.post(url, json=json)
            response.raise_for_status()
            logger.debug(f"成功发送请求到 {url}")
        except Exception as e:
            logger.error(f"发送请求到 {url} 失败: {e}")


_client = None


def get_hotkey_client() -> HotkeyClient:
    """Get the global HotkeyClient instance."""
    global _client
    if _client is None:
        _client = HotkeyClient()
    return _client
