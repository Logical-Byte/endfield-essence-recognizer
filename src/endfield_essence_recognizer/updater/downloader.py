"""更新下载模块"""

import asyncio
import time
from collections.abc import Callable
from pathlib import Path

import aiofiles
import certifi
import httpx

from endfield_essence_recognizer.utils.log import logger


async def download_update(
    download_url: str,
    save_path: Path,
    progress_callback: Callable[[int, int, float], None] | None = None,
    cancel_event: asyncio.Event | None = None,
    proxy: str | None = None,
) -> bool:
    """下载更新文件

    Args:
        download_url: 下载链接
        save_path: 保存路径
        progress_callback: 进度回调 (已下载, 总大小, 速度)
        cancel_event: 取消信号
        proxy: 代理地址

    Returns:
        bool: 下载是否成功
    """
    try:
        save_path.parent.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(
            timeout=300.0, verify=certifi.where(), follow_redirects=True, proxy=proxy
        ) as client:
            logger.info(f"开始下载更新: {download_url}")

            async with client.stream("GET", download_url) as response:
                response.raise_for_status()
                total_size = int(response.headers.get("content-length", 0))
                downloaded = 0
                start_time = time.time()

                async with aiofiles.open(save_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        if cancel_event and cancel_event.is_set():
                            logger.info("下载已取消")
                            break

                        await f.write(chunk)
                        downloaded += len(chunk)
                        elapsed = time.time() - start_time
                        speed = downloaded / elapsed if elapsed > 0 else 0

                        if progress_callback:
                            progress_callback(downloaded, total_size, speed)

        # 检查是否被取消
        if cancel_event and cancel_event.is_set():
            if await asyncio.to_thread(save_path.exists):
                await asyncio.to_thread(save_path.unlink)
            return False

        logger.info(f"更新下载完成: {save_path}")
        return True

    except asyncio.CancelledError:
        logger.info("下载已取消")
        if await asyncio.to_thread(save_path.exists):
            await asyncio.to_thread(save_path.unlink)
        return False
    except Exception as e:
        logger.error(f"下载更新失败: {e}")
        if await asyncio.to_thread(save_path.exists):
            await asyncio.to_thread(save_path.unlink)
        return False
