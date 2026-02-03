import pytest


def pytest_addoption(parser):
    # 添加 --ci 命令行参数
    parser.addoption(
        "--ci", action="store_true", default=False, help="表示当前运行环境为 CI"
    )


def pytest_collection_modifyitems(config, items):
    # 如果命令行没有带 --ci 参数，直接返回，正常运行所有测试
    if not config.getoption("--ci"):
        return

    # 如果带了 --ci 参数，遍历所有测试用例
    skip_ci = pytest.mark.skip(reason="此测试在 CI 环境中被跳过（需在本地运行）")
    for item in items:
        # 如果测试用例带有 'skip_in_ci' 标记，则给它打上 skip 标签
        if "skip_in_ci" in item.keywords:
            item.add_marker(skip_ci)
