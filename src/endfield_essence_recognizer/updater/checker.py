"""版本检查模块。"""

from __future__ import annotations

import re
from typing import Any

import certifi
import httpx
from packaging import version

from endfield_essence_recognizer.updater.sources import (
    GITHUB_FLOW,
    MIRROR_CHYAN_FLOW,
    YITULIU_FLOW,
    build_update_flow_order,
)
from endfield_essence_recognizer.utils.log import logger
from endfield_essence_recognizer.version import __version__

# 一图流版本检查 API。
UPDATE_CHECK_URL = (
    "https://cos.yituliu.cn/endfield/endfield-essence-recognizer/version.json"
)

# Mirror 酱检查更新 API；res_id 由 Mirror 酱后台分配。
MIRROR_CHYAN_LATEST_URL = "https://mirrorchyan.com/api/resources/{res_id}/latest"
MIRROR_CHYAN_DEFAULT_USER_AGENT = "EER_APP"

# GitHub Releases 检查 API。
GITHUB_REPO = "Logical-Byte/endfield-essence-recognizer"
GITHUB_LATEST_RELEASE_URL = (
    f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
)

# 从 GitHub Release 下载 URL 中提取 owner/repo/tag/filename。
_GITHUB_RELEASE_RE = re.compile(
    r"https://github\.com/([^/]+)/([^/]+)/releases/download/([^/]+)/(.+)"
)

# 版本源 JSON 可能由不同发布脚本生成，这里统一兼容常见字段名。
_INCREMENTAL_PACKAGE_KEYS = (
    "incrementalPackages",
    "incremental_packages",
    "deltaPackages",
    "patches",
)

# GitHub 增量包文件名中常见的标记词。
_INCREMENTAL_ASSET_MARKERS = ("delta", "incremental", "patch")
# 全量包文件名中应排除的标记词（包含增量包标记和版本分隔符）。
_FULL_ASSET_EXCLUDE_MARKERS = (*_INCREMENTAL_ASSET_MARKERS, "-to-", "_to_")


class UpdateCheckError(Exception):
    """更新检查失败（网络、解析、源站等错误）。"""

    def __init__(self, message: str) -> None:
        """保存可展示给调用方的更新检查失败原因。"""
        super().__init__(message)
        self.message = message


class NoUpdateAvailable:
    """标记：当前已是最新版本。"""

    pass


async def _fetch_github_release_sha256(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    tag: str,
    filename: str,
) -> str | None:
    """从 GitHub Releases API 获取指定 asset 的 sha256 digest。

    Args:
        client: 已创建的 httpx 异步客户端。
        owner: 仓库所有者。
        repo: 仓库名。
        tag: release tag。
        filename: asset 文件名。

    Returns:
        hex 格式的 sha256 字符串，或 None。
    """
    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}"
    try:
        resp = await client.get(
            api_url,
            headers={"Accept": "application/vnd.github+json"},
        )
        resp.raise_for_status()
        release_data = resp.json()

        for asset in release_data.get("assets", []):
            if asset.get("name") == filename:
                return _sha256_from_asset(asset)

        logger.info(f"GitHub asset {filename} 没有 digest 字段")
        return None
    except Exception as exc:
        logger.warning(f"获取 GitHub Release sha256 失败: {exc}")
        return None


def _get_first(data: dict, *keys: str) -> object | None:
    """按兼容字段名顺序返回第一个非空值。"""
    for key in keys:
        value = data.get(key)
        if value is not None:
            return value
    return None


def _normalize_version(value: object) -> str:
    """把可选 v 前缀版本号规范化为 packaging 可比较格式。"""
    return str(value or "").strip().removeprefix("v").removeprefix("V")


def _sha256_from_asset(asset: dict[str, Any]) -> str | None:
    """从 GitHub asset digest 字段中提取 sha256 十六进制字符串。"""
    digest = asset.get("digest", "")
    if isinstance(digest, str) and digest.startswith("sha256:"):
        return digest[len("sha256:") :]
    return None


async def _fetch_mirror_chyan_latest(
    client: httpx.AsyncClient,
    *,
    res_id: str,
    current_version: str,
    cdk: str | None,
    user_agent: str | None,
) -> dict:
    """调用 Mirror 酱最新版本接口，返回 data 字段或抛出可展示错误。"""
    params = {
        "current_version": current_version,
        "user_agent": user_agent or MIRROR_CHYAN_DEFAULT_USER_AGENT,
    }
    if cdk:
        params["cdk"] = cdk

    response = await client.get(
        MIRROR_CHYAN_LATEST_URL.format(res_id=res_id), params=params
    )
    try:
        payload = response.json()
    except ValueError as exc:
        response.raise_for_status()
        raise UpdateCheckError("Mirror 酱返回了无法解析的响应") from exc

    code = payload.get("code")
    if code != 0:
        msg = payload.get("msg") or payload.get("message") or "未知错误"
        raise UpdateCheckError(f"Mirror 酱检查更新失败: code={code}, msg={msg}")

    data = payload.get("data")
    if not isinstance(data, dict):
        raise UpdateCheckError("Mirror 酱响应缺少 data 对象")
    return data


def _find_incremental_package(data: dict, latest_version: str) -> dict | None:
    """从版本源中查找可从当前版本升级到最新版本的增量包。"""
    packages: object | None = None
    current_version = _normalize_version(__version__)
    target_version = _normalize_version(latest_version)
    for key in _INCREMENTAL_PACKAGE_KEYS:
        packages = data.get(key)
        if packages:
            break
    if not isinstance(packages, list):
        return None

    for package in packages:
        if not isinstance(package, dict):
            continue
        from_version = _get_first(package, "fromVersion", "from_version", "from")
        to_version = _get_first(package, "toVersion", "to_version", "to")
        if _normalize_version(from_version) != current_version:
            continue
        if to_version is None:
            logger.warning("跳过缺少明确 to_version 的增量包")
            continue
        if _normalize_version(to_version) != target_version:
            continue
        download_url = _get_first(package, "downloadUrl", "download_url", "url")
        if not isinstance(download_url, str) or not download_url:
            continue
        return package
    return None


async def _resolve_sha256(
    client: httpx.AsyncClient,
    url: str,
    explicit_sha256: object | None = None,
) -> str | None:
    """优先使用显式 sha256，再回退到 GitHub asset digest。"""
    if isinstance(explicit_sha256, str) and explicit_sha256:
        return explicit_sha256.removeprefix("sha256:")

    match = _GITHUB_RELEASE_RE.match(url)
    if not match:
        return None

    owner, repo, tag, filename = match.groups()
    return await _fetch_github_release_sha256(client, owner, repo, tag, filename)


def _yituliu_download_url(package: dict) -> str | None:
    """只接受一图流版本源中的 CN 镜像下载地址。"""
    mirrors = package.get("mirrors", {})
    if isinstance(mirrors, dict):
        for key in (YITULIU_FLOW, "cn"):
            mirror = mirrors.get(key)
            if isinstance(mirror, dict):
                download_url = mirror.get("downloadUrl") or mirror.get("download_url")
                if isinstance(download_url, str) and download_url:
                    return download_url
    return None


async def _check_yituliu_updates(
    client: httpx.AsyncClient,
) -> dict | NoUpdateAvailable:
    """只使用一图流 API 检查更新。"""
    response = await client.get(UPDATE_CHECK_URL)
    response.raise_for_status()
    data = response.json()

    latest_version = str(data["latestVersion"])
    if version.parse(latest_version) <= version.parse(__version__):
        logger.info("一图流返回当前已是最新版本")
        return NoUpdateAvailable()

    full_download_url = _yituliu_download_url(data)
    if not full_download_url:
        raise UpdateCheckError("一图流版本源缺少 cn_yituliu 下载地址")

    full_sha256 = await _resolve_sha256(
        client,
        full_download_url,
        _get_first(data, "sha256", "digest"),
    )
    update_info = {
        "version": latest_version,
        "download_url": full_download_url,
        "mirrors": data.get("mirrors", {}),
        "sha256": full_sha256,
        "package_type": "full",
        "source": YITULIU_FLOW,
        "full_download_url": full_download_url,
        "full_source": YITULIU_FLOW,
        "full_mirrors": data.get("mirrors", {}),
        "full_sha256": full_sha256,
        "full_size": data.get("size"),
    }

    incremental_package = _find_incremental_package(data, latest_version)
    if incremental_package:
        incremental_url = _yituliu_download_url(incremental_package)
        if incremental_url:
            incremental_sha256 = await _resolve_sha256(
                client,
                incremental_url,
                _get_first(incremental_package, "sha256", "digest"),
            )
            update_info.update(
                {
                    "download_url": incremental_url,
                    "mirrors": incremental_package.get("mirrors", {}),
                    "sha256": incremental_sha256,
                    "package_type": "incremental",
                    "from_version": __version__,
                    "size": incremental_package.get("size"),
                }
            )
            logger.info(f"一图流将优先使用增量包: {__version__} -> {latest_version}")
        else:
            logger.warning("一图流增量包缺少 cn_yituliu 下载地址，改用全量包")

    logger.info(f"一图流发现新版本 {latest_version}")
    return update_info


async def _check_mirror_chyan_updates(
    client: httpx.AsyncClient,
    *,
    mirror_chyan_res_id: str | None,
    mirror_chyan_cdk: str | None,
    mirror_chyan_user_agent: str | None,
) -> dict | NoUpdateAvailable:
    """只使用 Mirror 酱最新版本接口检查更新。"""
    if not isinstance(mirror_chyan_res_id, str) or not mirror_chyan_res_id.strip():
        raise UpdateCheckError("Mirror 酱流程未配置资源 ID")

    mirror_data = await _fetch_mirror_chyan_latest(
        client,
        res_id=mirror_chyan_res_id.strip(),
        current_version=f"v{__version__}",
        cdk=mirror_chyan_cdk.strip() if isinstance(mirror_chyan_cdk, str) else None,
        user_agent=mirror_chyan_user_agent,
    )
    mirror_latest = _normalize_version(mirror_data.get("version_name"))
    if not mirror_latest:
        raise UpdateCheckError("Mirror 酱响应缺少 version_name")

    if version.parse(mirror_latest) <= version.parse(__version__):
        logger.info("Mirror 酱返回当前已是最新版本")
        return NoUpdateAvailable()

    mirror_url = mirror_data.get("url")
    if not isinstance(mirror_url, str) or not mirror_url:
        raise UpdateCheckError("Mirror 酱未返回下载地址，请检查 CDK 或订阅状态")

    logger.info(f"Mirror 酱发现新版本 {mirror_latest}")
    return {
        "version": mirror_latest,
        "download_url": mirror_url,
        "mirrors": {},
        "sha256": None,
        "package_type": "mirror_chyan",
        "from_version": __version__,
        "source": MIRROR_CHYAN_FLOW,
        "release_note": mirror_data.get("release_note"),
        "size": mirror_data.get("size"),
    }


def _version_tokens(value: str) -> tuple[str, ...]:
    """生成版本号的常见写法，用于匹配 GitHub 增量包文件名。"""
    raw = _normalize_version(value)
    with_v = f"v{raw}"
    return (
        raw,
        with_v,
        raw.replace(".", "-"),
        with_v.replace(".", "-"),
    )


def _asset_url(asset: dict[str, Any]) -> str | None:
    """从 GitHub asset 对象中读取浏览器下载地址。"""
    url = asset.get("browser_download_url")
    return url if isinstance(url, str) and url else None


def _is_windows_zip_asset(asset: dict[str, Any]) -> bool:
    """判断 GitHub asset 是否为 Windows zip 更新包。"""
    name = str(asset.get("name") or "").lower()
    return name.endswith(".zip") and "windows" in name


def _find_github_full_asset(assets: list[dict[str, Any]]) -> dict[str, Any] | None:
    """从 GitHub assets 列表中选择全量 Windows 更新包。"""
    for asset in assets:
        name = str(asset.get("name") or "").lower()
        if not _is_windows_zip_asset(asset):
            continue
        if any(marker in name for marker in _FULL_ASSET_EXCLUDE_MARKERS):
            continue
        return asset
    for asset in assets:
        if _is_windows_zip_asset(asset):
            return asset
    return None


def _find_github_incremental_asset(
    assets: list[dict[str, Any]], latest_version: str
) -> dict[str, Any] | None:
    """从 GitHub assets 列表中选择当前版本到目标版本的增量包。"""
    current_tokens = _version_tokens(__version__)
    latest_tokens = _version_tokens(latest_version)
    for asset in assets:
        name = str(asset.get("name") or "").lower()
        if not _is_windows_zip_asset(asset):
            continue
        if not any(marker in name for marker in _INCREMENTAL_ASSET_MARKERS):
            continue
        if any(token.lower() in name for token in current_tokens) and any(
            token.lower() in name for token in latest_tokens
        ):
            return asset
    return None


async def _check_github_updates(
    client: httpx.AsyncClient,
) -> dict | NoUpdateAvailable:
    """只使用 GitHub Releases API 检查更新。"""
    response = await client.get(
        GITHUB_LATEST_RELEASE_URL,
        headers={"Accept": "application/vnd.github+json"},
    )
    response.raise_for_status()
    release_data = response.json()

    latest_version = _normalize_version(release_data.get("tag_name"))
    if not latest_version:
        raise UpdateCheckError("GitHub Release 响应缺少 tag_name")

    if version.parse(latest_version) <= version.parse(__version__):
        logger.info("GitHub 返回当前已是最新版本")
        return NoUpdateAvailable()

    raw_assets = release_data.get("assets", [])
    assets = [asset for asset in raw_assets if isinstance(asset, dict)]
    full_asset = _find_github_full_asset(assets)
    if not full_asset:
        raise UpdateCheckError("GitHub Release 缺少 Windows 全量更新包")
    full_url = _asset_url(full_asset)
    if not full_url:
        raise UpdateCheckError("GitHub Release 全量更新包缺少下载地址")

    full_sha256 = _sha256_from_asset(full_asset)
    update_info = {
        "version": latest_version,
        "download_url": full_url,
        "mirrors": {},
        "sha256": full_sha256,
        "package_type": "full",
        "source": GITHUB_FLOW,
        "full_download_url": full_url,
        "full_source": GITHUB_FLOW,
        "full_mirrors": {},
        "full_sha256": full_sha256,
        "full_size": full_asset.get("size"),
        "release_note": release_data.get("body"),
    }

    incremental_asset = _find_github_incremental_asset(assets, latest_version)
    if incremental_asset:
        incremental_url = _asset_url(incremental_asset)
        if incremental_url:
            update_info.update(
                {
                    "download_url": incremental_url,
                    "sha256": _sha256_from_asset(incremental_asset),
                    "package_type": "incremental",
                    "from_version": __version__,
                    "to_version": latest_version,
                    "size": incremental_asset.get("size"),
                }
            )
            logger.info(f"GitHub 将优先使用增量包: {__version__} -> {latest_version}")

    logger.info(f"GitHub 发现新版本 {latest_version}")
    return update_info


async def check_for_updates(
    proxy: str | None = None,
    update_flow: str | None = None,
    mirror_chyan_res_id: str | None = None,
    mirror_chyan_cdk: str | None = None,
    mirror_chyan_user_agent: str | None = None,
) -> dict | NoUpdateAvailable | UpdateCheckError:
    """按启用顺序检查是否有新版本。

    三种返回值互斥，调用方必须按类型分派：
    - dict → 有新版本
    - NoUpdateAvailable → 已是最新
    - UpdateCheckError → 所有启用流程均检查失败（不应被伪装成"没有更新"）

    返回的 dict 会优先指向可用增量包，并保留 full_download_url 作为全量包回退。
    dict 中可能包含 ``sha256`` 字段（显式配置或从 GitHub Releases API 获取），
    供下载后校验使用。

    Args:
        proxy: 代理地址（如 "http://127.0.0.1:7890"）。
        update_flow: 首选更新流程（cn_yituliu / cn_mirrorchyan / github）。
        mirror_chyan_res_id: Mirror 酱资源 ID。
        mirror_chyan_cdk: Mirror 酱 CDK。
        mirror_chyan_user_agent: Mirror 酱来源统计标识。

    Returns:
        见上方说明。
    """
    if not __version__:
        return UpdateCheckError("无法获取当前版本号")

    flow_order = build_update_flow_order(update_flow)
    if not flow_order:
        return UpdateCheckError("未启用任何更新流程")

    errors: list[str] = []
    try:
        async with httpx.AsyncClient(
            timeout=10.0, verify=certifi.where(), proxy=proxy or None
        ) as client:
            for flow in flow_order:
                try:
                    if flow == YITULIU_FLOW:
                        return await _check_yituliu_updates(client)
                    if flow == MIRROR_CHYAN_FLOW:
                        return await _check_mirror_chyan_updates(
                            client,
                            mirror_chyan_res_id=mirror_chyan_res_id,
                            mirror_chyan_cdk=mirror_chyan_cdk,
                            mirror_chyan_user_agent=mirror_chyan_user_agent,
                        )
                    if flow == GITHUB_FLOW:
                        return await _check_github_updates(client)
                    errors.append(f"{flow}: 未知更新流程")
                except UpdateCheckError as exc:
                    logger.warning(f"更新流程 {flow} 检查失败: {exc.message}")
                    errors.append(f"{flow}: {exc.message}")
                except Exception as exc:
                    logger.warning(f"更新流程 {flow} 检查失败: {exc}")
                    errors.append(f"{flow}: {exc}")
    except Exception as exc:
        logger.warning(f"检查更新失败: {exc}")
        return UpdateCheckError(str(exc))

    return UpdateCheckError("所有启用的更新流程均检查失败：" + "；".join(errors))
