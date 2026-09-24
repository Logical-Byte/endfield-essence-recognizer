"""测试静态文件的 MIME 类型映射（Windows 白屏问题修复验证）"""

import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from endfield_essence_recognizer.core.config import ServerConfig
from endfield_essence_recognizer.lifespan import init_mount_frontend_build


@pytest.fixture
def temp_dist_dir():
    """创建临时的前端构建目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        dist_path = Path(tmpdir)

        # 创建测试文件
        (dist_path / "test.js").write_text("console.log('test');")
        (dist_path / "test.css").write_text("body { margin: 0; }")

        yield dist_path


def test_static_files_mime_types(temp_dist_dir):
    """验证静态文件返回正确的 Content-Type（防止 Windows 白屏问题）"""
    app = FastAPI()
    config = ServerConfig(dev_mode=False, dist_dir=str(temp_dist_dir))

    init_mount_frontend_build(app, config)
    client = TestClient(app)

    # 测试 .js 文件
    response = client.get("/test.js")
    assert response.status_code == 200
    assert "application/javascript" in response.headers["content-type"]

    # 测试 .css 文件
    response = client.get("/test.css")
    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]
