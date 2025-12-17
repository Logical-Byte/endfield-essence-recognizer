"""窗口截图和区域捕获工具模块。"""

from collections.abc import Container

import numpy as np
import pygetwindow
import win32con
import win32gui
import win32ui
from cv2.typing import MatLike


def get_window_hwnd(window: pygetwindow.Window) -> int:
    """获取 `pygetwindow` 窗口对象的窗口句柄"""
    hwnd = window._hWnd
    if not hwnd:
        # 通过窗口标题查找窗口句柄
        hwnd = win32gui.FindWindow(None, window.title)
        if not hwnd:
            # 如果找不到精确匹配，遍历所有窗口查找包含关键词的
            def callback(h, extra):
                if window.title in win32gui.GetWindowText(h):
                    extra.append(h)

            hwnds = []
            win32gui.EnumWindows(callback, hwnds)
            if hwnds:
                hwnd = hwnds[0]
            else:
                raise RuntimeError(f"Cannot find hwnd of window {window}")
    return hwnd


def get_client_rect(window: pygetwindow.Window) -> dict[str, int]:
    """获取窗口客户区的屏幕坐标（不包含标题栏和边框）"""

    # 获取窗口句柄
    hwnd = get_window_hwnd(window)

    # 获取客户区矩形
    # GetClientRect 返回 (left, top, right, bottom)，客户区左上角为 (0, 0)
    client_rect = win32gui.GetClientRect(hwnd)
    left, top, right, bottom = client_rect

    # 将客户区左上角转换为屏幕坐标
    left_top = win32gui.ClientToScreen(hwnd, (left, top))
    # 将客户区右下角转换为屏幕坐标
    right_bottom = win32gui.ClientToScreen(hwnd, (right, bottom))

    return {
        "left": left_top[0],
        "top": left_top[1],
        "right": right_bottom[0],
        "bottom": right_bottom[1],
        "width": right_bottom[0] - left_top[0],
        "height": right_bottom[1] - left_top[1],
    }


def screenshot_by_win32ui(rect: tuple[int, int, int, int]) -> MatLike:
    """
    截取屏幕指定区域，返回 BGR 格式的 numpy 图像。

    Args:
        rect: 矩形区域 (left, top, right, bottom) 的屏幕坐标

    Returns:
        numpy 数组（BGR 格式，OpenCV 兼容）
    """
    left, top, right, bottom = rect
    width, height = right - left, bottom - top
    if width <= 0 or height <= 0:
        raise ValueError(f"Try to screenshot with invalid rect: {rect}")

    # 创建设备上下文和位图
    screen_dc = win32gui.GetDC(0)
    img_dc = win32ui.CreateDCFromHandle(screen_dc)
    mem_dc = img_dc.CreateCompatibleDC()

    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(img_dc, width, height)
    mem_dc.SelectObject(bitmap)

    # 复制屏幕区域到位图
    mem_dc.BitBlt((0, 0), (width, height), img_dc, (left, top), win32con.SRCCOPY)

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

    # 释放 GDI 资源
    mem_dc.DeleteDC()
    img_dc.DeleteDC()
    win32gui.ReleaseDC(0, screen_dc)
    win32gui.DeleteObject(bitmap.GetHandle())

    return arr.copy()


def screenshot_window(
    window: pygetwindow.Window, relative_region: tuple[int, int, int, int] | None = None
) -> MatLike:
    """
    截取指定窗口的客户区，返回 BGR 格式的 numpy 图像。

    Args:
        window: pygetwindow 窗口对象

    Returns:
        numpy 数组（BGR 格式，OpenCV 兼容）
    """
    client_rect = get_client_rect(window)
    left = client_rect["left"]
    top = client_rect["top"]
    right = client_rect["right"]
    bottom = client_rect["bottom"]
    if relative_region is not None:
        rx1, ry1, rx2, ry2 = relative_region
        left += rx1
        top += ry1
        right = left + (rx2 - rx1)
        bottom = top + (ry2 - ry1)
    # return screenshot_by_pyautogui((left, top, right, bottom))
    return screenshot_by_win32ui((left, top, right, bottom))


def get_active_support_window(
    supported_window_titles: Container[str],
) -> pygetwindow.Window | None:
    active_window = pygetwindow.getActiveWindow()
    if active_window is not None and active_window.title in supported_window_titles:
        return active_window
    else:
        return None
