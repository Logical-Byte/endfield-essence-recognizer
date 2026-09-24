from __future__ import annotations

import pytest

from endfield_essence_recognizer.updater import checker
from endfield_essence_recognizer.updater.sources import (
    GITHUB_FLOW,
    MIRROR_CHYAN_FLOW,
    YITULIU_FLOW,
)


class FakeResponse:
    """用于模拟 httpx 响应对象的最小测试替身。"""

    def __init__(self, payload: dict, *, status_error: Exception | None = None) -> None:
        """保存响应 JSON 与可选状态码异常。"""
        self.payload = payload
        self.status_error = status_error

    def json(self) -> dict:
        """返回预设 JSON 响应。"""
        return self.payload

    def raise_for_status(self) -> None:
        """按预设结果模拟状态码异常。"""
        if self.status_error:
            raise self.status_error


class FakeAsyncClient:
    """用于记录请求 URL 并按 URL 返回预设响应的异步客户端。"""

    calls: list[str] = []
    routes: dict[str, FakeResponse | Exception] = {}

    def __init__(self, *args, **kwargs) -> None:
        """兼容 httpx.AsyncClient 的构造参数。"""
        pass

    async def __aenter__(self) -> FakeAsyncClient:
        """模拟异步上下文管理器进入。"""
        return self

    async def __aexit__(self, *args) -> None:
        """模拟异步上下文管理器退出。"""
        return

    async def get(self, url: str, **kwargs) -> FakeResponse:
        """记录请求并返回预设响应；未预设的 URL 视为测试失败。"""
        self.calls.append(url)
        result = self.routes.get(url)
        if isinstance(result, Exception):
            raise result
        if result is None:
            raise AssertionError(f"未预期的请求: {url}")
        return result


@pytest.fixture(autouse=True)
def fake_httpx(monkeypatch):
    """为每个用例重置并替换网络客户端，避免真实联网。"""
    FakeAsyncClient.calls = []
    FakeAsyncClient.routes = {}
    monkeypatch.setattr(checker.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(checker, "__version__", "1.0.0")


@pytest.mark.asyncio
async def test_yituliu_flow_only_requests_yituliu():
    """一图流流程只应请求一图流版本源。"""
    FakeAsyncClient.routes = {
        checker.UPDATE_CHECK_URL: FakeResponse(
            {
                "latestVersion": "1.1.0",
                "mirrors": {
                    YITULIU_FLOW: {
                        "downloadUrl": "https://cos.yituliu.cn/eer-1.1.0.zip"
                    }
                },
            }
        )
    }

    result = await checker.check_for_updates(update_flow=YITULIU_FLOW)

    assert isinstance(result, dict)
    assert result["source"] == YITULIU_FLOW
    assert FakeAsyncClient.calls == [checker.UPDATE_CHECK_URL]


@pytest.mark.asyncio
async def test_mirror_chyan_flow_only_requests_mirror_chyan(monkeypatch):
    """Mirror 酱流程只应请求 Mirror 酱接口。"""
    # mirror_chyan 在当前版本默认禁用，测试时临时启用以验证独立流程
    from endfield_essence_recognizer.updater import sources

    monkeypatch.setitem(sources.UPDATE_FLOW_ENABLED, sources.MIRROR_CHYAN_FLOW, True)

    mirror_url = checker.MIRROR_CHYAN_LATEST_URL.format(res_id="EER")
    FakeAsyncClient.routes = {
        mirror_url: FakeResponse(
            {
                "code": 0,
                "data": {
                    "version_name": "v1.1.0",
                    "url": "https://mirrorchyan.com/resources/download/token",
                },
            }
        )
    }

    result = await checker.check_for_updates(
        update_flow=MIRROR_CHYAN_FLOW,
        mirror_chyan_res_id="EER",
        mirror_chyan_cdk="测试CDK",
    )

    assert isinstance(result, dict)
    assert result["source"] == MIRROR_CHYAN_FLOW
    assert FakeAsyncClient.calls == [mirror_url]


@pytest.mark.asyncio
async def test_github_flow_only_requests_github():
    """GitHub 流程只应请求 GitHub Releases API。"""
    FakeAsyncClient.routes = {
        checker.GITHUB_LATEST_RELEASE_URL: FakeResponse(
            {
                "tag_name": "v1.1.0",
                "assets": [
                    {
                        "name": "endfield-essence-recognizer-v1.1.0-windows.zip",
                        "browser_download_url": (
                            "https://github.com/Logical-Byte/"
                            "endfield-essence-recognizer/releases/download/"
                            "v1.1.0/endfield-essence-recognizer-v1.1.0-windows.zip"
                        ),
                        "digest": "sha256:" + "a" * 64,
                    }
                ],
            }
        )
    }

    result = await checker.check_for_updates(update_flow=GITHUB_FLOW)

    assert isinstance(result, dict)
    assert result["source"] == GITHUB_FLOW
    assert FakeAsyncClient.calls == [checker.GITHUB_LATEST_RELEASE_URL]


@pytest.mark.asyncio
async def test_failed_checks_fallback_in_enabled_order_to_github():
    """检查失败时应按启用顺序回退到后续流程。"""
    FakeAsyncClient.routes = {
        checker.UPDATE_CHECK_URL: RuntimeError("一图流不可用"),
        checker.GITHUB_LATEST_RELEASE_URL: FakeResponse(
            {
                "tag_name": "v1.1.0",
                "assets": [
                    {
                        "name": "endfield-essence-recognizer-v1.1.0-windows.zip",
                        "browser_download_url": (
                            "https://github.com/Logical-Byte/"
                            "endfield-essence-recognizer/releases/download/"
                            "v1.1.0/endfield-essence-recognizer-v1.1.0-windows.zip"
                        ),
                    }
                ],
            }
        ),
    }

    result = await checker.check_for_updates(update_flow=YITULIU_FLOW)

    assert isinstance(result, dict)
    assert result["source"] == GITHUB_FLOW
    assert FakeAsyncClient.calls == [
        checker.UPDATE_CHECK_URL,
        checker.GITHUB_LATEST_RELEASE_URL,
    ]
