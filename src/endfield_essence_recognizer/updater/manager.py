"""更新管理器。"""

import asyncio
import hashlib
from collections.abc import Callable
from pathlib import Path

from endfield_essence_recognizer.updater.checker import (
    NoUpdateAvailable,
    UpdateCheckError,
    check_for_updates,
)
from endfield_essence_recognizer.updater.downloader import download_update
from endfield_essence_recognizer.updater.installer import install_update
from endfield_essence_recognizer.utils.log import logger


class UpdateManager:
    """更新管理器。"""

    def __init__(self, download_dir: Path | None = None):
        """初始化更新状态、下载目录和并发控制对象。"""
        self.download_dir = download_dir or Path.cwd() / "_updates"
        self.update_info: dict | None = None
        self.cancel_event = asyncio.Event()
        self.is_downloading = False
        self.download_lock = asyncio.Lock()
        self.download_task: asyncio.Task | None = None

    async def check_and_prompt(
        self,
        proxy: str | None = None,
        update_flow: str | None = None,
        mirror_chyan_res_id: str | None = None,
        mirror_chyan_cdk: str | None = None,
        mirror_chyan_user_agent: str | None = None,
    ) -> dict | NoUpdateAvailable | UpdateCheckError:
        """检查更新并返回更新信息。

        返回值由 checker 的三种类型决定，调用方必须按类型分派。
        如果发现新版本，会缓存 update_info，供后续下载和安装使用。
        """
        result = await check_for_updates(
            proxy=proxy,
            update_flow=update_flow,
            mirror_chyan_res_id=mirror_chyan_res_id,
            mirror_chyan_cdk=mirror_chyan_cdk,
            mirror_chyan_user_agent=mirror_chyan_user_agent,
        )
        if isinstance(result, dict):
            self.update_info = result
        return result

    def _compute_sha256(self, file_path: Path) -> str:
        """计算文件 SHA-256，供前端展示实际值。"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    async def _download_verify_install(
        self,
        *,
        url: str,
        download_path: Path,
        expected_hash: str | None,
        progress_callback: Callable[[int, int, float], None] | None,
        proxy: str | None,
        skip_verify: bool,
    ) -> dict:
        """下载指定更新包，完成可选哈希校验后交给安装器执行。

        返回值：
        - {"success": True} → 安装成功
        - {"success": False, "error": "xxx"} → 一般下载或安装错误
        - {"success": False, "error": "sha256_mismatch", ...} → 哈希校验失败
        """
        self.download_task = asyncio.create_task(
            download_update(
                url,
                download_path,
                progress_callback,
                self.cancel_event,
                proxy,
            )
        )
        success = await self.download_task

        if not success:
            return {"success": False, "error": "下载失败或已取消"}

        if expected_hash and not skip_verify:
            actual_hash = await asyncio.to_thread(self._compute_sha256, download_path)
            if actual_hash != expected_hash:
                logger.error(
                    f"SHA-256 校验失败: 期望 {expected_hash[:16]}... "
                    f"实际 {actual_hash[:16]}..."
                )
                return {
                    "success": False,
                    "error": "sha256_mismatch",
                    "sha256_expected": expected_hash,
                    "sha256_actual": actual_hash,
                }
            logger.info("SHA-256 校验通过")
        elif expected_hash and skip_verify:
            logger.warning("用户选择跳过 SHA-256 校验")
        else:
            logger.info("无可用的 sha256 校验值，跳过完整性验证")

        install_ok = await asyncio.to_thread(install_update, download_path)
        if install_ok:
            return {"success": True}
        return {"success": False, "error": "安装失败"}

    async def download_and_install(
        self,
        progress_callback: Callable[[int, int, float], None] | None = None,
        proxy: str | None = None,
        download_url: str | None = None,
        skip_verify: bool = False,
    ) -> dict:
        """下载并安装更新。

        返回值：
        - {"success": True} → 安装成功
        - {"success": False, "error": "xxx"} → 一般错误
        - {"success": False, "error": "sha256_mismatch", ...} → 校验失败

        增量包失败回退策略：
        - 增量包下载成功但安装前校验或安装流程失败时，自动回退到全量包。
        - 增量包 SHA-256 不匹配时不自动回退，必须交给前端提示用户确认风险。
        """
        async with self.download_lock:
            if not self.update_info:
                logger.warning("没有可用的更新信息")
                return {"success": False, "error": "没有可用的更新信息"}

            version = self.update_info["version"]
            package_type = self.update_info.get("package_type", "full")
            download_path = self.download_dir / f"update_{version}_{package_type}.zip"

            self.cancel_event.clear()
            self.is_downloading = True

            try:
                url = download_url or self.update_info["download_url"]
                result = await self._download_verify_install(
                    url=url,
                    download_path=download_path,
                    expected_hash=self.update_info.get("sha256"),
                    progress_callback=progress_callback,
                    proxy=proxy,
                    skip_verify=skip_verify,
                )
                if result.get("success"):
                    return result

                full_url = self.update_info.get("full_download_url")
                # 仅在增量包的普通安装失败时回退全量包；哈希不匹配必须显式提示用户。
                should_fallback = (
                    package_type in {"incremental"}
                    and result.get("error") != "sha256_mismatch"
                    and isinstance(full_url, str)
                    and full_url
                    and full_url != url
                    and self.update_info.get("source")
                    == self.update_info.get("full_source")
                    and not self.cancel_event.is_set()
                )
                if not should_fallback:
                    return result

                logger.warning("增量包安装失败，自动回退到全量包")
                full_path = self.download_dir / f"update_{version}_full.zip"
                return await self._download_verify_install(
                    url=full_url,
                    download_path=full_path,
                    expected_hash=self.update_info.get("full_sha256"),
                    progress_callback=progress_callback,
                    proxy=proxy,
                    skip_verify=skip_verify,
                )
            except Exception as exc:
                logger.error(f"更新流程异常: {exc}")
                return {"success": False, "error": str(exc)}
            finally:
                self.is_downloading = False
                self.download_task = None

    def cancel_download(self) -> bool:
        """取消下载。"""
        if self.is_downloading and self.download_task and not self.download_task.done():
            self.cancel_event.set()
            self.download_task.cancel()
            logger.info("已发送取消下载信号")
            return True
        logger.warning("当前没有正在进行的下载")
        return False
