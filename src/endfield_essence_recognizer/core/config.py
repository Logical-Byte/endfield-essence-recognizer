"""
Configuration of the server process.

Provides constants and configuration variables used across the server. The configuration
is primarily set by the `.env` file.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import TYPE_CHECKING

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from webview.guilib import GUI_TYPES, GUIType

if TYPE_CHECKING:
    from pathlib import Path


class LogLevel(StrEnum):
    """Logging level enumeration."""

    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ServerConfig(BaseSettings):
    """
    Configuration class for the server process.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="EER_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        use_enum_values=True,
    )

    log_level: LogLevel = Field(
        default=LogLevel.INFO,
    )
    """
    EER_LOG_LEVEL: 控制台和 WebSocket 的日志输出等级。
    """

    dev_mode: bool = Field(
        default=False,
    )
    """
    EER_DEV_MODE: 是否启用开发模式。
    """

    dist_dir: str = Field(
        default="",
    )
    """
    EER_DIST_DIR: 前端构建文件目录。
    """

    dev_url: str = Field(
        default="http://localhost:3000",
    )
    """
    EER_DEV_URL: 开发模式下前端应用的 URL。
    """

    api_host: str = Field(
        default="localhost",
    )
    """
    EER_API_HOST: 服务器主机地址。
    """

    api_port: int = Field(
        default=325,
    )
    """
    EER_API_PORT: 服务器端口号。
    """

    webview_debug: bool = Field(
        default=False,
    )
    """
    EER_WEBVIEW_DEBUG: 是否启用 Webview 调试模式。
    """

    webview_gui: GUIType | None = Field(
        default=None,
    )
    f"""
    EER_WEBVIEW_GUI: Webview 使用的 GUI 后端，默认为 None，表示自动选择。可选值包括：{", ".join(GUI_TYPES)}。
    """

    def _get_webview_prod_url(self) -> str:
        """生产环境 Webview URL"""
        return f"http://localhost:{self.api_port}"

    @computed_field
    @property
    def webview_url(self) -> str:
        """Webview 使用的 URL"""
        return self.dev_url if self.dev_mode else self._get_webview_prod_url()


def _get_fresh_server_config(
    base_dir: Path | None = None, use_dotenv: bool = True
) -> ServerConfig:
    """
    Get a fresh server configuration instance, bypassing the cache.

    Args:
        base_dir (Path | None): Optional base directory to locate the `.env` file. If None,
            should load the default `.env` file which is at the same directory as whatever
            is __main__.
        use_dotenv (bool): Whether to use the `.env` file for configuration. If False, pass
            _env_file=None to ServerConfig to ignore any .env files.
    """
    if not use_dotenv:
        return ServerConfig(_env_file=None)  # type: ignore
    if base_dir is None:
        return ServerConfig()
    return ServerConfig(_env_file=base_dir / ".env")  # type: ignore


@lru_cache(maxsize=1)
def get_server_config() -> ServerConfig:
    """
    Get the singleton server configuration instance.

    This function takes no parameters and returns a cached `ServerConfig` instance,
    initialized using the default configuration loading behavior.
    """
    return _get_fresh_server_config(base_dir=None, use_dotenv=True)
