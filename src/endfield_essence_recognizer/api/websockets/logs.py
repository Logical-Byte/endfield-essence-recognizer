from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from endfield_essence_recognizer.dependencies import get_log_service
from endfield_essence_recognizer.services.log_service import LogService
from endfield_essence_recognizer.utils.log import logger

router = APIRouter(prefix="", tags=["logs"])


@router.websocket("/logs")
async def websocket_logs(
    websocket: WebSocket,
    log_service: LogService = Depends(get_log_service),
):
    await websocket.accept()
    await log_service.add_connection(websocket)
    logger.info("WebSocket 日志连接已建立。")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("WebSocket 日志连接已断开。")
    except Exception as e:
        logger.exception(f"WebSocket 日志连接出错：{e}")
    finally:
        log_service.remove_connection(websocket)
