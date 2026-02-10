import httpx

from endfield_essence_recognizer.core.config import get_server_config
from endfield_essence_recognizer.utils.log import logger


class HotkeyClient:
    """A minimal HTTP client for sending commands to the local FastAPI server."""

    def __init__(self):
        config = get_server_config()
        self.base_url = f"http://{config.api_host}:{config.api_port}/api"
        self.client = httpx.Client(timeout=5.0)

    def post(
        self, endpoint: str, json: dict | None = None, key_pressed: str = ""
    ) -> None:
        """Send a POST request to the backend."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        caller = f"Hotkey '{key_pressed}'" if key_pressed else "HotkeyClient"
        try:
            response = self.client.post(url, json=json)
            response.raise_for_status()
            logger.debug(f"成功发送请求到 {url}")
        except httpx.HTTPStatusError as e:
            # this means the server returned an error response
            # we expect that server has logged the error details
            # we only log as the hotkey client
            response_body = e.response.text
            status_code = e.response.status_code
            logger.warning(
                f"{caller} 发送请求到 {url} 后发生错误：{status_code}, 响应内容: {response_body}"
            )
        except Exception as e:
            logger.warning(f"{caller} 发送请求到 {url} 失败: {e}")


_client = None


def get_hotkey_client() -> HotkeyClient:
    """Get the global HotkeyClient instance."""
    global _client
    if _client is None:
        _client = HotkeyClient()
    return _client
