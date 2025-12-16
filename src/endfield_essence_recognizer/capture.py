"""窗口截图和区域捕获工具模块。"""

import logging
from ctypes import byref, windll, wintypes

import cv2
import numpy as np
import win32con
import win32gui
import win32ui


def get_client_rect_screen(hwnd: int) -> tuple[int, int, int, int]:
    """
    获取窗口客户区在屏幕上的位置和大小。

    Args:
        hwnd: 窗口句柄

    Returns:
        (left, top, width, height) 元组，表示客户区的屏幕坐标和尺寸
    """
    rect = wintypes.RECT()
    windll.user32.GetClientRect(hwnd, byref(rect))
    width = rect.right - rect.left
    height = rect.bottom - rect.top

    point = wintypes.POINT(rect.left, rect.top)
    windll.user32.ClientToScreen(hwnd, byref(point))

    return point.x, point.y, width, height


def capture_client_roi_np(
    hwnd: int, rect: tuple[int, int, int, int]
) -> np.ndarray | None:
    """
    抓取窗口客户区内指定 ROI 区域，返回 BGR 格式的 numpy 图像。

    此函数用于在内存中直接获取屏幕区域的像素数据，无需保存文件，
    适合实时图像识别场景。

    Args:
        hwnd: 窗口句柄
        rect: ROI 矩形，使用客户区像素坐标 (x1, y1, x2, y2)
            - x1, y1: 左上角坐标（相对于客户区左上角）
            - x2, y2: 右下角坐标（相对于客户区左上角）

    Returns:
        numpy 数组（BGR 格式，OpenCV 兼容），失败时返回 None

    技术细节：
        - 将客户区坐标转换为屏幕坐标
        - 使用 GDI BitBlt 复制屏幕区域
        - 读取位图原始字节并转换为 numpy 数组
        - 处理字节对齐（stride）和颜色通道顺序
        - 自动丢弃 alpha 通道（如果存在）

    注意：
        函数中包含 cv2.imshow 调试代码，生产环境应注释掉。
    """
    try:
        x1, y1, x2, y2 = rect
        if x2 <= x1 or y2 <= y1:
            return None

        # 计算屏幕绝对坐标
        left, top, _, _ = get_client_rect_screen(hwnd)
        abs_x, abs_y = left + x1, top + y1
        width, height = x2 - x1, y2 - y1

        # 创建设备上下文和位图
        screen_dc = win32gui.GetDC(0)
        img_dc = win32ui.CreateDCFromHandle(screen_dc)
        mem_dc = img_dc.CreateCompatibleDC()

        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(img_dc, width, height)
        mem_dc.SelectObject(bitmap)

        # 复制屏幕区域到位图
        mem_dc.BitBlt((0, 0), (width, height), img_dc, (abs_x, abs_y), win32con.SRCCOPY)

        # 读取位图像素数据
        bmpinfo = bitmap.GetInfo()
        bpp = bmpinfo["bmBitsPixel"] // 8  # 每像素字节数（通常为3或4）
        stride = ((width * bpp + 3) // 4) * 4  # 4字节对齐的行宽
        raw = bitmap.GetBitmapBits(True)

        # 转换为 numpy 数组
        arr = np.frombuffer(raw, dtype=np.uint8)
        arr = arr.reshape((height, stride))
        arr = arr[:, : width * bpp]  # 移除对齐填充
        arr = arr.reshape((height, width, bpp))

        # 如果是 BGRA 格式，转换为 BGR
        if bpp == 4:
            arr = arr[:, :, :3]  # 丢弃 alpha 通道

        # 调试：显示 ROI 区域（生产环境应注释）
        cv2.imshow("Debug ROI", arr)

        # 释放 GDI 资源
        mem_dc.DeleteDC()
        img_dc.DeleteDC()
        win32gui.ReleaseDC(0, screen_dc)
        win32gui.DeleteObject(bitmap.GetHandle())

        return arr.copy()
    except Exception as e:
        logging.exception(f"capture_client_roi_np failed: {e}")
        return None
