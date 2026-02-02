"""
Windows OS-specific window utilities.
"""

from collections.abc import Sequence

import numpy as np
import pyautogui
import pygetwindow
import win32con
import win32gui  # ty:ignore[unresolved-import]
import win32ui  # ty:ignore[unresolved-import]
from cv2.typing import MatLike

from endfield_essence_recognizer.utils.image import Scope


def _get_window_hwnd(window: pygetwindow.Window) -> int:
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


def get_client_size(window: pygetwindow.Window) -> tuple[int, int]:
    """获取窗口客户区的尺寸（宽度和高度）"""
    hwnd = _get_window_hwnd(window)
    client_left, client_top, client_right, client_bottom = win32gui.GetClientRect(hwnd)
    width = client_right - client_left
    height = client_bottom - client_top
    return width, height


def _get_client_rect(window: pygetwindow.Window) -> Scope:
    """获取窗口客户区的屏幕坐标（不包含标题栏和边框）"""

    # 获取窗口句柄
    hwnd = _get_window_hwnd(window)

    # 获取客户区矩形
    # GetClientRect 返回 (left, top, right, bottom)，客户区左上角为 (0, 0)
    client_rect = win32gui.GetClientRect(hwnd)
    client_left, client_top, client_right, client_bottom = client_rect

    # 将客户区左上角转换为屏幕坐标
    left, top = win32gui.ClientToScreen(hwnd, (client_left, client_top))
    # 将客户区右下角转换为屏幕坐标
    right, bottom = win32gui.ClientToScreen(hwnd, (client_right, client_bottom))

    return ((left, top), (right, bottom))


def _screenshot_by_win32ui(scope: Scope) -> MatLike:
    """
    截取屏幕指定区域，返回 BGR 格式的 numpy 图像。

    Args:
        scope: 屏幕区域，格式为 ((left, top), (right, bottom))

    Returns:
        numpy 数组（BGR 格式，OpenCV 兼容）
    """
    (left, top), (right, bottom) = scope
    width, height = right - left, bottom - top
    if width <= 0 or height <= 0:
        raise ValueError(f"Try to screenshot with invalid rect: {scope}")

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
    window: pygetwindow.Window, relative_region: Scope | None = None
) -> MatLike:
    """
    截取指定窗口的客户区，返回 BGR 格式的 numpy 图像。

    Args:
        window: pygetwindow 窗口对象

    Returns:
        numpy 数组（BGR 格式，OpenCV 兼容）
    """
    client_rect = _get_client_rect(window)
    (left, top), (_right, _bottom) = client_rect
    if relative_region is not None:
        (rx1, ry1), (rx2, ry2) = relative_region
        scope = ((left + rx1, top + ry1), (left + rx2, top + ry2))
    else:
        scope = client_rect
    return _screenshot_by_win32ui(scope)


def get_support_window(
    supported_window_titles: Sequence[str],
) -> pygetwindow.Window | None:
    """
    Try to get a window that matches one of the supported titles. The order of
    titles indicates the priority of selection. Strict string match is performed.

    Args:
        supported_window_titles: Sequence of supported window titles. The order
            indicates the priority of selection.

    Returns:
        A `pygetwindow.Window` object if a matching window is found, otherwise None.
    """
    all_windows: list[pygetwindow.Window] = pygetwindow.getAllWindows()
    for title in supported_window_titles:
        # do strict match
        strict_matches = [w for w in all_windows if w.title == title]
        if strict_matches:
            return strict_matches[0]
    return None


def click_on_window(
    window: pygetwindow.Window, relative_x: int, relative_y: int
) -> None:
    """在指定窗口的客户区坐标 (x, y) 位置点击"""
    (left, top), (_right, _bottom) = _get_client_rect(window)
    screen_x = left + relative_x
    screen_y = top + relative_y
    pyautogui.click(screen_x, screen_y)
