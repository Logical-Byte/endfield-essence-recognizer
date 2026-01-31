import pytest

from endfield_essence_recognizer.core.config import ServerConfig, get_server_config


@pytest.fixture(autouse=True)
def clear_config_cache():
    """Clear the configuration cache before each test to ensure isolation."""
    get_server_config.cache_clear()
    yield


def test_server_config_defaults():
    """Test that ServerConfig has correct default values."""
    # We use a clean environment for this test to avoid local .env interference
    config = ServerConfig(_env_file=None)
    assert config.dev_mode is False
    assert config.api_host == "localhost"
    assert config.api_port == 8000
    assert config.dev_url == "http://localhost:3000"
    assert config.prod_url == "http://localhost:8000"
    assert config.webview_url == "http://localhost:8000"


def test_server_config_computed_properties():
    """Test computed properties prod_url and webview_url."""
    # Production mode
    config_prod = ServerConfig(dev_mode=False, api_port=8080, _env_file=None)
    assert config_prod.prod_url == "http://localhost:8080"
    assert config_prod.webview_url == "http://localhost:8080"

    # Development mode
    config_dev = ServerConfig(
        dev_mode=True, dev_url="http://localhost:5173", _env_file=None
    )
    assert config_dev.webview_url == "http://localhost:5173"


def test_server_config_env_override(monkeypatch):
    """Test that environment variables override default values."""
    monkeypatch.setenv("EER_DEV_MODE", "true")
    monkeypatch.setenv("EER_API_PORT", "9999")
    monkeypatch.setenv("EER_DIST_DIR", "/tmp/dist")

    # Passing _env_file=None to ignore any existing .env files
    config = ServerConfig(_env_file=None)
    assert config.dev_mode is True
    assert config.api_port == 9999
    assert config.dist_dir == "/tmp/dist"


def test_get_server_config_singleton():
    """Test that get_server_config returns a singleton instance."""
    config1 = get_server_config()
    config2 = get_server_config()
    assert config1 is config2


def test_get_server_config_with_base_dir(tmp_path):
    """Test that get_server_config correctly loads from a specified directory."""
    env_content = "EER_API_PORT=7777\nEER_DEV_MODE=true\nEER_API_HOST=127.0.0.1\n"
    env_file = tmp_path / ".env"
    env_file.write_text(env_content)

    # Calling with base_dir should load the .env from that dir
    config = get_server_config(base_dir=tmp_path)
    assert config.api_port == 7777
    assert config.dev_mode is True
    assert config.api_host == "127.0.0.1"

    # Verify it cached this specific configuration (though usually we'd only use one)
    config_cached = get_server_config(base_dir=tmp_path)
    assert config_cached is config
