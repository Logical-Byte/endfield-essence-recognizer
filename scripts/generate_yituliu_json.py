"""从最新 GitHub Release 生成一图流 version.json。

通过 GitHub REST API 获取 Release 信息，下载资产计算 SHA-256，
输出符合一图流版本源格式的 JSON 文件。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

_DEFAULT_REPO = "Logical-Byte/endfield-essence-recognizer"
_DEFAULT_CDN_BASE = "https://cos.yituliu.cn/endfield/endfield-essence-recognizer"
_GITHUB_API = "https://api.github.com"


def _fetch_latest_release(repo: str) -> dict:
    """通过 GitHub REST API 获取最新 Release 数据。"""
    url = f"{_GITHUB_API}/repos/{repo}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def _compute_sha256(url: str) -> str:
    """下载远程文件并计算 SHA-256。"""
    sha256 = hashlib.sha256()
    with urllib.request.urlopen(url) as resp:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()


def _digest_from_asset(asset: dict) -> str | None:
    """从 GitHub asset 的 digest 字段提取 sha256，不存在则返回 None。"""
    digest = asset.get("digest", "")
    if isinstance(digest, str) and digest.startswith("sha256:"):
        return digest[len("sha256:") :]
    return None


def _parse_full_asset(
    asset: dict[str, str | int],
    version: str,
) -> dict | None:
    """解析全量包 asset，返回简化信息或 None。"""
    name = asset.get("name", "")
    if not isinstance(name, str):
        return None
    expected = f"endfield-essence-recognizer-v{version}-windows.zip"
    if name != expected:
        return None
    url = asset.get("browser_download_url", "")
    if not isinstance(url, str):
        return None
    return {"name": name, "url": url, "size": asset.get("size", 0), "_raw": asset}


def _parse_incremental_asset(asset: dict[str, str | int]) -> dict | None:
    """解析增量包 asset，返回 (from_version, to_version, info) 或 None。

    匹配格式：incremental-v{from}-to-{to}-windows.zip
    """
    name = asset.get("name", "")
    if not isinstance(name, str):
        return None
    if not name.startswith("incremental-v"):
        return None
    if not name.endswith("-windows.zip"):
        return None

    # incremental-v0.9.2-to-v0.9.3-windows.zip
    # 去掉前缀 "incremental-v" 和后缀 "-windows.zip"
    inner = name[len("incremental-v") : -len("-windows.zip")]
    # inner = "0.9.2-to-v0.9.3"
    parts = inner.split("-to-")
    if len(parts) != 2:
        return None

    from_ver = parts[0]  # "0.9.2"
    to_ver = parts[1].lstrip("v")  # "v0.9.3" -> "0.9.3"

    url = asset.get("browser_download_url", "")
    if not isinstance(url, str):
        return None

    return {
        "from_version": from_ver,
        "to_version": to_ver,
        "name": name,
        "url": url,
        "size": asset.get("size", 0),
        "_raw": asset,
    }


def _build_mirrors(
    github_url: str,
    cdn_base: str,
    filename: str,
) -> dict:
    """构建 mirrors 对象。"""
    return {
        "global": {"downloadUrl": github_url},
        "cn": {"downloadUrl": f"{cdn_base}/{filename}"},
    }


def generate_yituliu_json(
    repo: str = _DEFAULT_REPO,
    cdn_base: str = _DEFAULT_CDN_BASE,
    skip_sha256: bool = False,
    use_api: bool = False,
) -> dict:
    """获取最新 Release 并生成一图流 version.json 的内容。

    Args:
        skip_sha256: 跳过 SHA-256，输出中不含 sha256 字段。
        use_api: 直接从 GitHub API 的 asset digest 字段读取 sha256，
                 不下载文件；若 asset 无 digest 则 sha256 为空。
    """
    release = _fetch_latest_release(repo)
    tag = release.get("tag_name", "")
    latest_version = tag.lstrip("v")
    raw_assets = release.get("assets", [])

    # 筛选 windows zip 资产
    assets = [a for a in raw_assets if isinstance(a, dict)]

    # 查找全量包
    full_info = None
    for asset in assets:
        full_info = _parse_full_asset(asset, latest_version)
        if full_info:
            break

    if not full_info:
        raise RuntimeError(
            f"未找到全量包: endfield-essence-recognizer-v{latest_version}-windows.zip"
        )

    # 查找增量包
    incremental_list = []
    for asset in assets:
        info = _parse_incremental_asset(asset)
        if info and info["to_version"] == latest_version:
            incremental_list.append(info)

    # 构建全量包信息
    full_sha256 = None
    if not skip_sha256:
        if use_api:
            full_sha256 = _digest_from_asset(full_info["_raw"])
            if not full_sha256:
                print(
                    f"警告: 全量包 {full_info['name']} 无 digest 字段", file=sys.stderr
                )
        else:
            print(f"计算全量包 SHA-256: {full_info['name']} ...", file=sys.stderr)
            full_sha256 = _compute_sha256(full_info["url"])

    result: dict = {
        "latestVersion": latest_version,
        "downloadUrl": full_info["url"],
        "mirrors": _build_mirrors(full_info["url"], cdn_base, full_info["name"]),
    }
    if full_sha256:
        result["sha256"] = full_sha256
    if full_info["size"]:
        result["size"] = full_info["size"]

    # 构建增量包列表
    inc_packages = []
    for inc in incremental_list:
        inc_sha256 = None
        if not skip_sha256:
            if use_api:
                inc_sha256 = _digest_from_asset(inc["_raw"])
                if not inc_sha256:
                    print(f"警告: 增量包 {inc['name']} 无 digest 字段", file=sys.stderr)
            else:
                print(f"计算增量包 SHA-256: {inc['name']} ...", file=sys.stderr)
                inc_sha256 = _compute_sha256(inc["url"])

        pkg: dict = {
            "fromVersion": inc["from_version"],
            "toVersion": inc["to_version"],
            "downloadUrl": inc["url"],
            "mirrors": _build_mirrors(inc["url"], cdn_base, inc["name"]),
        }
        if inc_sha256:
            pkg["sha256"] = inc_sha256
        if inc["size"]:
            pkg["size"] = inc["size"]
        inc_packages.append(pkg)

    result["incrementalPackages"] = inc_packages

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="从最新 GitHub Release 生成一图流 version.json",
    )
    parser.add_argument(
        "--repo",
        default=_DEFAULT_REPO,
        help=f"GitHub 仓库 (默认: {_DEFAULT_REPO})",
    )
    parser.add_argument(
        "--cdn-base",
        default=_DEFAULT_CDN_BASE,
        help=f"一图流 CDN 基础地址 (默认: {_DEFAULT_CDN_BASE})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="输出文件路径 (默认: 输出到 stdout)",
    )
    parser.add_argument(
        "--skip-sha256",
        action="store_true",
        help="跳过下载文件计算 SHA-256",
    )
    parser.add_argument(
        "--use-api",
        action="store_true",
        help="直接从 GitHub API 的 asset digest 字段读取 sha256，不下载文件",
    )
    args = parser.parse_args()

    result = generate_yituliu_json(
        repo=args.repo,
        cdn_base=args.cdn_base,
        skip_sha256=args.skip_sha256,
        use_api=args.use_api,
    )

    output = json.dumps(result, indent=2, ensure_ascii=False) + "\n"

    if args.output:
        args.output.write_text(output, encoding="utf-8")
        print(f"已写入: {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
