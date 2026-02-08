import os

import pytest
from _pytest.config import Config
from _pytest.config.argparsing import Parser
from _pytest.nodes import Item


def pytest_addoption(parser: Parser):
    # 添加 --ci 命令行参数
    parser.addoption(
        "--ci", action="store_true", default=False, help="表示当前运行环境为 CI"
    )


# register skip_in_ci marker
def pytest_configure(config: Config):
    config.addinivalue_line(
        "markers", "skip_in_ci: 标记此测试在 CI 环境中被跳过（需在本地运行）"
    )

    is_ci = config.getoption("--ci") or os.getenv("GITHUB_ACTIONS") == "true"

    config._ci_mode = is_ci


def pytest_runtest_setup(item: Item):
    # 检查是否设置了 --ci 参数
    if item.config._ci_mode and item.get_closest_marker("skip_in_ci"):
        pytest.skip("跳过在 CI 环境中运行的测试")
