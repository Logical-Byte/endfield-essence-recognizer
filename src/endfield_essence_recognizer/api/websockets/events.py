"""结构化事件 WebSocket：前端订阅后台任务完成事件（如扫描完成）"""

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from endfield_essence_recognizer.dependencies import get_event_service
from endfield_essence_recognizer.services.event_service import EventService
from endfield_essence_recognizer.utils.log import logger

router = APIRouter(prefix="", tags=["events"])


@router.websocket("/events")
async def websocket_events(
    websocket: WebSocket,
    event_service: EventService = Depends(get_event_service),
):
    await websocket.accept()
    await event_service.add_connection(websocket)
    logger.info("Event WebSocket 连接已建立。")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("Event WebSocket 连接已断开。")
    except Exception as exc:
        logger.exception(f"Event WebSocket 连接出错：{exc}")
    finally:
        event_service.remove_connection(websocket)
