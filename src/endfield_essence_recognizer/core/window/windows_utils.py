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

from endfield_essence_recognizer.core.layout.base import Point, Region


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


def _get_client_rect(window: pygetwindow.Window) -> Region:
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

    return Region(Point(left, top), Point(right, bottom))


def _screenshot_by_win32ui(scope: Region) -> MatLike:
    """
    截取屏幕指定区域，返回 BGR 格式的 numpy 图像。

    Args:
        scope: 屏幕区域

    Returns:
        numpy 数组（BGR 格式，OpenCV 兼容）
    """
    left, top, right, bottom = scope.x0, scope.y0, scope.x1, scope.y1
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
    window: pygetwindow.Window, relative_region: Region | None = None
) -> MatLike:
    """
    截取指定窗口的客户区，返回 BGR 格式的 numpy 图像。

    Args:
        window: pygetwindow 窗口对象

    Returns:
        numpy 数组（BGR 格式，OpenCV 兼容）
    """
    client_rect = _get_client_rect(window)
    if relative_region is not None:
        scope = Region(
            Point(
                client_rect.x0 + relative_region.x0, client_rect.y0 + relative_region.y0
            ),
            Point(
                client_rect.x0 + relative_region.x1, client_rect.y0 + relative_region.y1
            ),
        )
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


def drag_on_window(
    window: pygetwindow.Window,
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    duration: float = 0.5,
    hold_time: float = 0.3,
) -> None:
    """
    在指定窗口的客户区执行鼠标拖动操作。

    拖动到目标位置后会保持按住状态一段时间，防止列表惯性滑动。

    Args:
        window: pygetwindow 窗口对象
        start_x: 相对于客户区左上角的起点 X 坐标
        start_y: 相对于客户区左上角的起点 Y 坐标
        end_x: 相对于客户区左上角的终点 X 坐标
        end_y: 相对于客户区左上角的终点 Y 坐标
        duration: 拖动持续时间（秒）
        hold_time: 拖动到终点后保持按住的时间（秒）
    """
    import time

    (left, top), (_right, _bottom) = _get_client_rect(window)
    screen_start_x = left + start_x
    screen_start_y = top + start_y
    screen_end_x = left + end_x
    screen_end_y = top + end_y

    # 移动到起点并按下鼠标
    pyautogui.moveTo(screen_start_x, screen_start_y)
    pyautogui.mouseDown()
    # 等待UI响应点击
    time.sleep(0.2)
    # 拖动到终点
    pyautogui.moveTo(screen_end_x, screen_end_y, duration=duration)
    # 保持按住状态，防止惯性滑动
    time.sleep(hold_time)
    # 松开鼠标
    pyautogui.mouseUp()
