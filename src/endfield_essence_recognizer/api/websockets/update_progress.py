"""更新进度 WebSocket"""

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from endfield_essence_recognizer.utils.log import logger

router = APIRouter(prefix="/update", tags=["update"])

# 全局进度状态
# total_known: 服务端是否提供了 content-length（为 false 时前端应显示"下载中…"而非百分比）
progress_state = {
    "downloaded": 0,
    "total": 0,
    "total_known": False,
    "speed": 0,
    "progress": 0,
}
_lock = asyncio.Lock()


def reset_progress() -> None:
    """重置进度状态，在每次新下载/安装开始前调用。"""
    progress_state.update(
        downloaded=0,
        total=0,
        total_known=False,
        speed=0,
        progress=0,
    )


@router.websocket("/progress")
async def update_progress_ws(websocket: WebSocket):
    """更新进度 WebSocket"""
    await websocket.accept()
    try:
        while True:
            async with _lock:
                data = progress_state.copy()
            await websocket.send_json(data)
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket 错误: {e}")


def update_progress(downloaded: int, total: int, speed: float):
    """更新进度状态

    Args:
        downloaded: 已下载字节数
        total: 总字节数（0 表示未知）
        speed: 当前下载速度 (bytes/s)
    """
    known = total > 0
    pct = (downloaded / total * 100) if known else 0

    async def _update():
        async with _lock:
            progress_state["downloaded"] = downloaded
            progress_state["total"] = total
            progress_state["total_known"] = known
            progress_state["speed"] = speed
            progress_state["progress"] = pct

    def _log_task_exception(task: asyncio.Task):
        try:
            task.result()
        except Exception as e:
            logger.error(f"更新进度任务失败: {e}")

    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(_update())
        task.add_done_callback(_log_task_exception)
    except RuntimeError:
        # 同步上下文中直接更新
        progress_state["downloaded"] = downloaded
        progress_state["total"] = total
        progress_state["total_known"] = known
        progress_state["speed"] = speed
        progress_state["progress"] = pct
