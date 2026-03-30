"""测试静态文件的 MIME 类型映射（Windows 白屏问题修复验证）"""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from endfield_essence_recognizer.core.config import ServerConfig
from endfield_essence_recognizer.lifespan import init_mount_frontend_build

# ============================================================
# Fixture
# ============================================================


@pytest.fixture
def temp_dist_dir(tmp_path: Path):
    """创建模拟前端构建产物的临时目录结构.

    结构:
        tmp/
        ├── index.html
        ├── favicon.ico
        ├── assets/
        │   ├── index-abc123.js          (带 hash 的 JS)
        │   ├── index-abc123.js.map      (source map)
        │   ├── index-def456.css         (带 hash 的 CSS)
        │   ├── chunk-xyz.mjs           (ESM 模块)
        │   ├── logo.svg
        │   ├── icon.png
        │   ├── photo.jpg
        │   ├── animation.gif
        │   ├── data.json
        │   ├── config.xml
        │   ├── robots.txt
        │   ├── manifest.webmanifest
        │   └── fonts/
        │       ├── inter-regular.woff2
        │       ├── inter-regular.woff
        │       └── inter-regular.ttf
        └── deep/
            └── nested/
                └── dir/
                    └── component.js
    """
    assets = tmp_path / "assets"
    fonts = assets / "fonts"
    deep = tmp_path / "deep" / "nested" / "dir"
    fonts.mkdir(parents=True)
    deep.mkdir(parents=True)

    files: dict[str, str] = {
        # 根目录
        "index.html": "<!DOCTYPE html><html></html>",
        "favicon.ico": "fake-ico",
        # assets/
        "assets/index-abc123.js": "console.log('chunk');",
        "assets/index-abc123.js.map": '{"version":3}',
        "assets/index-def456.css": "body{margin:0}",
        "assets/chunk-xyz.mjs": "export default 42;",
        "assets/logo.svg": "<svg></svg>",
        "assets/icon.png": "fake-png",
        "assets/photo.jpg": "fake-jpg",
        "assets/animation.gif": "fake-gif",
        "assets/data.json": '{"key":"value"}',
        "assets/config.xml": "<root/>",
        "assets/robots.txt": "User-agent: *",
        "assets/manifest.webmanifest": '{"name":"app"}',
        # assets/fonts/
        "assets/fonts/inter-regular.woff2": "fake-woff2",
        "assets/fonts/inter-regular.woff": "fake-woff",
        "assets/fonts/inter-regular.ttf": "fake-ttf",
        # deep nested
        "deep/nested/dir/component.js": "export const C = 1;",
    }

    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)

    return tmp_path


@pytest.fixture
def app_client(temp_dist_dir: Path):
    """构建挂载了前端静态文件的 FastAPI 测试客户端."""
    app = FastAPI()
    config = ServerConfig(dev_mode=False, dist_dir=str(temp_dist_dir))
    init_mount_frontend_build(app, config)
    return TestClient(app)


# ============================================================
# MIME 类型映射表 —— 新增文件类型只需在此处追加
# ============================================================

MIME_CASES: list[tuple[str, str]] = [
    # --- 脚本 ---
    ("/assets/index-abc123.js", "application/javascript"),
    (
        "/assets/chunk-xyz.mjs",
        "javascript",
    ),  # .mjs 可能返回 application/javascript 或 text/javascript
    # --- 样式 ---
    ("/assets/index-def456.css", "text/css"),
    # --- 标记 / 数据 ---
    ("/index.html", "text/html"),
    ("/assets/logo.svg", "image/svg+xml"),
    ("/assets/data.json", "application/json"),
    ("/assets/config.xml", "application/xml"),
    ("/assets/robots.txt", "text/plain"),
    (
        "/assets/manifest.webmanifest",
        "application/manifest+json",
    ),  # 部分环境可能回落到 application/json
    # --- 图片 ---
    ("/assets/icon.png", "image/png"),
    ("/assets/photo.jpg", "image/jpeg"),
    ("/assets/animation.gif", "image/gif"),
    ("/favicon.ico", "image/x-icon"),  # 也可能是 image/vnd.microsoft.icon
    # --- 字体 ---
    ("/assets/fonts/inter-regular.woff2", "font/woff2"),
    ("/assets/fonts/inter-regular.woff", "font/woff"),
    ("/assets/fonts/inter-regular.ttf", "font/ttf"),  # 也可能是 application/font-sfnt
    # --- Source Map ---
    ("/assets/index-abc123.js.map", "application/json"),
]


# ============================================================
# 测试用例
# ============================================================


class TestMimeTypes:
    """验证各类前端资源返回正确的 Content-Type."""

    @pytest.mark.parametrize(
        "path,expected_mime", MIME_CASES, ids=[p for p, _ in MIME_CASES]
    )
    def test_mime_type(self, app_client: TestClient, path: str, expected_mime: str):
        resp = app_client.get(path)
        assert resp.status_code == 200, f"{path} 返回 {resp.status_code}，期望 200"
        content_type = resp.headers["content-type"]
        assert expected_mime in content_type, (
            f"{path} 的 Content-Type 为 {content_type!r}，期望包含 {expected_mime!r}"
        )


class TestHashedFilenames:
    """Vite/Webpack 构建产物通常带有 content-hash，确保路径解析不受影响."""

    def test_hashed_js_resolved(self, app_client: TestClient):
        resp = app_client.get("/assets/index-abc123.js")
        assert resp.status_code == 200
        assert "application/javascript" in resp.headers["content-type"]

    def test_hashed_css_resolved(self, app_client: TestClient):
        resp = app_client.get("/assets/index-def456.css")
        assert resp.status_code == 200
        assert "text/css" in resp.headers["content-type"]

    def test_source_map_resolved(self, app_client: TestClient):
        resp = app_client.get("/assets/index-abc123.js.map")
        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]


class TestSubdirectoryPaths:
    """验证多层嵌套目录下的文件仍能正确服务."""

    def test_deep_nested_js(self, app_client: TestClient):
        resp = app_client.get("/deep/nested/dir/component.js")
        assert resp.status_code == 200
        assert "application/javascript" in resp.headers["content-type"]

    def test_font_subdirectory(self, app_client: TestClient):
        resp = app_client.get("/assets/fonts/inter-regular.woff2")
        assert resp.status_code == 200
        assert "font/woff2" in resp.headers["content-type"]

    def test_root_level_file(self, app_client: TestClient):
        """根目录 index.html 直接可访问."""
        resp = app_client.get("/index.html")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


class TestNotFound:
    """验证不存在的路径返回 404 而非 500."""

    def test_missing_file_returns_404(self, app_client: TestClient):
        resp = app_client.get("/nonexistent.js")
        assert resp.status_code == 404

    def test_missing_nested_file_returns_404(self, app_client: TestClient):
        resp = app_client.get("/assets/no-such-file.xyz")
        assert resp.status_code == 404

    def test_missing_directory_returns_404(self, app_client: TestClient):
        resp = app_client.get("/no-such-dir/file.js")
        assert resp.status_code == 404


class TestPathTraversal:
    """防止目录穿越攻击."""

    def test_dotdot_blocked(self, app_client: TestClient):
        resp = app_client.get("/../../../etc/passwd")
        # FastAPI StaticFiles 会将此规范化，要么 404，要么返回 dist 内的文件
        # 绝不应泄露系统文件
        assert resp.status_code in (400, 404)


class TestCaseSensitivity:
    """Windows 文件系统不区分大小写，Linux 区分.
    验证在目标部署环境下行为一致.
    """

    def test_uppercase_extension(self, app_client: TestClient):
        """请求 .JS 大写 —— 在 Linux 上可能 404，Windows 上可能 200.
        这里只验证不会 500.
        """
        resp = app_client.get("/assets/index-abc123.JS")
        assert resp.status_code in (200, 404)

    def test_mixed_case_extension(self, app_client: TestClient):
        resp = app_client.get("/assets/index-def456.Css")
        assert resp.status_code in (200, 404)


class TestResponseHeaders:
    """验证响应头的附加属性."""

    def test_js_content_type_charset(self, app_client: TestClient):
        """JS 文件 Content-Type 不应包含错误的 charset 声明."""
        resp = app_client.get("/assets/index-abc123.js")
        ct = resp.headers["content-type"]
        # 允许无 charset 或 charset=utf-8，但不能有 charset=iso-8859-1 等
        assert "iso-8859" not in ct.lower()

    def test_binary_file_no_text_content_type(self, app_client: TestClient):
        """二进制文件（图片、字体）不应被错误地标记为 text/plain."""
        resp = app_client.get("/assets/icon.png")
        ct = resp.headers["content-type"].lower()
        assert "text/plain" not in ct

    def test_content_length_present(self, app_client: TestClient):
        """静态文件应返回 Content-Length."""
        resp = app_client.get("/assets/index-abc123.js")
        assert "content-length" in resp.headers
        assert int(resp.headers["content-length"]) > 0


class TestFileContent:
    """验证返回的文件内容正确."""

    def test_js_content_integrity(self, app_client: TestClient):
        resp = app_client.get("/assets/index-abc123.js")
        assert resp.text == "console.log('chunk');"

    def test_css_content_integrity(self, app_client: TestClient):
        resp = app_client.get("/assets/index-def456.css")
        assert "margin:0" in resp.text

    def test_json_content_integrity(self, app_client: TestClient):
        resp = app_client.get("/assets/data.json")
        assert resp.json() == {"key": "value"}

    def test_html_content_integrity(self, app_client: TestClient):
        resp = app_client.get("/index.html")
        assert "<!DOCTYPE html>" in resp.text
