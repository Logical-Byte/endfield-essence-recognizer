"""
Windows OS-specific window utilities.
"""

import time
from collections.abc import Callable, Sequence

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

    try:
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

        return arr.copy()
    finally:
        mem_dc.DeleteDC()
        img_dc.DeleteDC()
        win32gui.ReleaseDC(0, screen_dc)
        win32gui.DeleteObject(bitmap.GetHandle())


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


def progressive_drag_on_window(
    window: pygetwindow.Window,
    relative_start_x: int,
    relative_start_y: int,
    relative_end_x: int,
    relative_end_y: int,
    step: int = 50,
    max_drag: int = 0,
    on_step: Callable[[int, int, int], bool] | None = None,
) -> tuple[int, bool]:
    """
    在指定窗口执行渐进式拖动，支持每步回调检测。

    鼠标按住不放，逐步移动，可在每步后进行滚动条检测。

    Args:
        window: pygetwindow 窗口对象
        relative_start_x: 拖动起始 X 坐标（相对于客户区）
        relative_start_y: 拖动起始 Y 坐标（相对于客户区）
        relative_end_x: 拖动终止 X 坐标（相对于客户区）
        relative_end_y: 拖动终止 Y 坐标（相对于客户区）
        step: 每次拖动的像素数
        max_drag: 最大拖动距离（0 表示不限制）
        on_step: 每步回调函数，参数为 (step_index, screen_x, screen_y)，
                  返回 True 表示提前停止拖动

    Returns:
        (total_distance, stopped_early) 总拖动距离和是否提前停止
    """
    (left, top), (_right, _bottom) = _get_client_rect(window)

    # 计算屏幕坐标
    screen_start_x = left + relative_start_x
    screen_start_y = top + relative_start_y
    screen_end_x = left + relative_end_x
    screen_end_y = top + relative_end_y

    # 计算总拖动距离和方向
    total_dx = screen_end_x - screen_start_x
    total_dy = screen_end_y - screen_start_y
    total_distance = int((total_dx**2 + total_dy**2) ** 0.5)

    # 限制最大拖动距离
    if max_drag > 0 and total_distance > max_drag:
        scale = max_drag / total_distance
        total_dx = int(total_dx * scale)
        total_dy = int(total_dy * scale)
        total_distance = max_drag

    # 计算步数和每步偏移
    steps = max(1, total_distance // step)
    step_distance = total_distance / steps

    # 移动到起点并按住鼠标
    pyautogui.moveTo(screen_start_x, screen_start_y)
    pyautogui.mouseDown()
    time.sleep(0.2)

    actual_distance = 0
    stopped_early = False

    try:
        for i in range(steps):
            # 计算当前步位置
            progress = (i + 1) / steps
            current_x = int(screen_start_x + total_dx * progress)
            current_y = int(screen_start_y + total_dy * progress)

            # 移动鼠标并等待游戏处理
            pyautogui.moveTo(current_x, current_y)
            time.sleep(0.05)

            # 先检测滚动条，再累加距离
            # 这样当检测到到底时，当前这一步的距离不会被计入
            if on_step is not None:
                if on_step(i, current_x, current_y):
                    stopped_early = True
                    break

            # 检测通过后才累加距离
            actual_distance += step_distance

        return int(actual_distance), stopped_early

    finally:
        time.sleep(0.5)  # 防止移动后UI惯性滑动
        pyautogui.mouseUp()
