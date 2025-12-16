"""
明日方舟终末地基质识别工具

这是一个用于自动化《明日方舟：终末地》游戏操作的辅助工具，主要功能包括：
1. 自动跳过对话 (热键 I)
2. 扫描基质图标并识别属性 (热键 O)
3. 截取游戏窗口截图 (热键 P)
4. 单次识别当前ROI区域文本 (热键 U)

技术特点：
- 完全基于 Win32 API，不依赖 pyautogui/pygetwindow/pynput
- 使用 GDI 进行窗口截图，支持精确的客户区定位
- 使用 OpenCV 模板匹配进行文本识别
- 支持中文路径的图片加载

作者: [Your Name]
日期: 2025-12-16
"""

import logging
import signal
import time
import winsound
from ctypes import byref, windll, wintypes
from datetime import datetime
from pathlib import Path

import numpy as np
import win32api
import win32con
import win32gui
import win32ui

from endfield_essence_recognizer.auto_skipper import AutoSkipper
from endfield_essence_recognizer.capture import (
    capture_client_roi_np,
    get_client_rect_screen,
)
from endfield_essence_recognizer.essence_scanner import EssenceScanner
from endfield_essence_recognizer.recognizer import BONUS_ROI, Recognizer

# ============================================================================
# 日志配置
# ============================================================================
logging.basicConfig(
    level=logging.DEBUG,
    format="{asctime}.{msecs:03.0f} [{levelname}] {module}:{funcName}:{lineno} | {message}",  # noqa: E501
    datefmt="%Y-%m-%d %H:%M:%S",
    style="{",
)

# ============================================================================
# 全局常量配置
# ============================================================================

# 目录路径
BASE_DIR = Path(__file__).parent
enable_sound_path: Path = BASE_DIR / "sound/enable.wav"  # 功能启用时的提示音
disable_sound_path: Path = BASE_DIR / "sound/disable.wav"  # 功能禁用时的提示音
screenshots_dir: Path = BASE_DIR / "screenshots"  # 截图保存目录

# 支持的游戏窗口标题列表
supported_window_titles: list[str] = ["EndfieldTBeta2"]

# 自动跳过对话的点击位置（相对于客户区的比例坐标，范围 0-1）
skip_conversation_clicks: tuple[float, float] = (0.7160, 0.7444)
skip_conversation_click_interval: float = 0.1  # 自动点击间隔（秒）

# 热键 ID 定义
HOTKEY_ID_TOGGLE_SKIP = 1  # I 键：切换自动跳过对话
HOTKEY_ID_SCAN = 2  # O 键：扫描基质图标
HOTKEY_ID_SCREENSHOT = 3  # P 键：截图
HOTKEY_ID_RECOGNIZE = 4  # U 键：单次识别

# 基质图标位置网格（客户区像素坐标）
# 9列5行，共45个图标位置
essence_icon_x_list = np.linspace(128, 1374, 9).astype(int)
essence_icon_y_list = np.linspace(196, 819, 5).astype(int)
icon_pos_grid = np.array(
    [(x, y) for y in essence_icon_y_list for x in essence_icon_x_list]
)

# 全局停止标志（用于优雅退出）
_should_exit = False


# ============================================================================
# 系统工具函数
# ============================================================================


def set_dpi_awareness() -> None:
    """
    设置进程 DPI 感知模式。

    在高 DPI 显示器上，Windows 会对未声明 DPI 感知的程序进行缩放，
    导致坐标计算不准确。调用此函数可以让程序获取真实的像素坐标。

    注意：此函数应在程序启动时尽早调用。
    """
    try:
        windll.user32.SetProcessDPIAware()
    except Exception:  # noqa: BLE001
        # 在某些系统上可能失败，忽略错误
        pass


def play_sound(path: Path | None) -> None:
    """
    异步播放音效文件。

    Args:
        path: 音频文件路径（WAV格式），如果路径不存在或为None则不播放
    """
    if not path or not path.is_file():
        return
    winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)


# ============================================================================
# 窗口操作函数
# ============================================================================


def get_window_title(hwnd: int) -> str:
    """
    获取窗口标题。

    Args:
        hwnd: 窗口句柄

    Returns:
        窗口标题字符串，失败时返回空字符串
    """
    try:
        return win32gui.GetWindowText(hwnd)
    except Exception:  # noqa: BLE001
        return ""


def is_supported_window(hwnd: int | None) -> bool:
    """
    检查窗口是否为支持的游戏窗口。

    Args:
        hwnd: 窗口句柄

    Returns:
        如果窗口标题在支持列表中返回 True，否则返回 False
    """
    if not hwnd:
        return False
    title = get_window_title(hwnd)
    return title in supported_window_titles


def client_pos_from_ratio(hwnd: int, rx: float, ry: float) -> tuple[int, int]:
    """
    根据相对比例计算客户区内的绝对屏幕坐标。

    Args:
        hwnd: 窗口句柄
        rx: X方向的相对位置（0.0 到 1.0，0 表示左边缘，1 表示右边缘）
        ry: Y方向的相对位置（0.0 到 1.0，0 表示上边缘，1 表示下边缘）

    Returns:
        (x, y) 元组，表示屏幕绝对坐标

    Example:
        # 点击客户区中心
        x, y = client_pos_from_ratio(hwnd, 0.5, 0.5)
    """
    left, top, width, height = get_client_rect_screen(hwnd)
    x = round(left + rx * width)
    y = round(top + ry * height)
    return x, y


# ============================================================================
# 输入操作函数
# ============================================================================


def send_left_click(x: int, y: int) -> None:
    """
    在指定屏幕坐标执行鼠标左键单击。

    Args:
        x: 屏幕X坐标（像素）
        y: 屏幕Y坐标（像素）

    注意：
        - 坐标必须是屏幕绝对坐标
        - 此函数会移动鼠标光标到目标位置
        - 点击是瞬时的（按下后立即释放）
    """
    win32api.SetCursorPos((x, y))
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def screenshot_client(hwnd: int) -> Path | None:
    """
    使用纯 Win32 GDI API 截取窗口客户区并保存为 BMP 文件。

    此函数只截取窗口的客户区（不含标题栏、边框和阴影），
    使用 GDI BitBlt 直接从屏幕复制像素数据，速度快且不依赖第三方库。

    Args:
        hwnd: 窗口句柄

    Returns:
        保存的截图文件路径，失败时返回 None

    技术细节：
        1. 获取窗口客户区的屏幕坐标
        2. 创建设备上下文（DC）和兼容位图
        3. 使用 BitBlt 复制屏幕区域到内存位图
        4. 保存位图为 BMP 文件
        5. 正确释放所有 GDI 资源，避免内存泄漏
    """
    try:
        left, top, width, height = get_client_rect_screen(hwnd)

        # 获取屏幕设备上下文
        screen_dc = win32gui.GetDC(0)
        img_dc = win32ui.CreateDCFromHandle(screen_dc)
        mem_dc = img_dc.CreateCompatibleDC()

        # 创建与屏幕兼容的位图对象
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(img_dc, width, height)
        mem_dc.SelectObject(bitmap)

        # 使用 BitBlt 从屏幕复制像素数据到内存位图
        mem_dc.BitBlt((0, 0), (width, height), img_dc, (left, top), win32con.SRCCOPY)

        # 生成带时间戳的文件名并保存
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
        path = screenshots_dir / f"screenshot-{ts}.bmp"
        bitmap.SaveBitmapFile(mem_dc, str(path))

        # 清理 GDI 资源
        mem_dc.DeleteDC()
        img_dc.DeleteDC()
        win32gui.ReleaseDC(0, screen_dc)
        win32gui.DeleteObject(bitmap.GetHandle())

        logging.info(f"Screenshot (client) saved: {path}")
        return path
    except Exception as e:
        logging.exception(f"Failed to take screenshot: {e}")
        return None


# ============================================================================
# 热键注册与处理函数
# ============================================================================


def register_hotkeys() -> None:
    """
    注册全局热键。

    注册以下热键到 Windows 系统：
    - I: 切换自动跳过对话开关
    - O: 开始/中断基质图标扫描
    - P: 截取当前窗口客户区
    - U: 执行一次 ROI 文本识别

    注意：
        - 这些热键在系统范围内生效，即使程序窗口不在前台
        - 但只有当游戏窗口在前台时，热键才会触发相应操作
        - 程序退出时必须调用 unregister_hotkeys() 释放热键
    """
    # I 键：切换自动跳过
    windll.user32.RegisterHotKey(None, HOTKEY_ID_TOGGLE_SKIP, 0, ord("I"))
    # O 键：扫描基质图标
    windll.user32.RegisterHotKey(None, HOTKEY_ID_SCAN, 0, ord("O"))
    # P 键：截图
    windll.user32.RegisterHotKey(None, HOTKEY_ID_SCREENSHOT, 0, ord("P"))
    # U 键：单次识别
    windll.user32.RegisterHotKey(None, HOTKEY_ID_RECOGNIZE, 0, ord("U"))

    logging.info("Hotkeys: I(toggle skip), O(scan), P(snap), U(recognize)")


def unregister_hotkeys() -> None:
    """
    注销所有全局热键。

    释放之前注册的所有热键，允许其他程序使用这些按键。
    此函数应在程序退出时调用。
    """
    for _id in (
        HOTKEY_ID_TOGGLE_SKIP,
        HOTKEY_ID_SCAN,
        HOTKEY_ID_SCREENSHOT,
        HOTKEY_ID_RECOGNIZE,
    ):
        try:
            windll.user32.UnregisterHotKey(None, _id)
        except Exception:  # noqa: BLE001
            # 忽略注销失败的错误
            pass


def toggle_essence_scan(scanner: "EssenceScanner") -> None:
    """
    切换基质扫描状态。

    Args:
        scanner: EssenceScanner 实例

    此函数在用户按下 O 键时被调用，会先验证前台窗口，
    然后调用 scanner.start_scan() 开始或中断扫描。
    """
    hwnd = win32gui.GetForegroundWindow()
    if not is_supported_window(hwnd):
        return
    scanner.start_scan()


# ============================================================================
# 信号处理与主程序
# ============================================================================


def signal_handler(sig, frame) -> None:
    """
    处理系统中断信号（Ctrl+C 或 SIGTERM）。

    Args:
        sig: 信号编号
        frame: 当前堆栈帧

    此函数设置全局退出标志并向消息循环发送退出消息，
    使程序能够优雅地响应 Ctrl+C 中断。
    """
    global _should_exit
    logging.info("Received interrupt signal, exiting...")
    _should_exit = True
    windll.user32.PostQuitMessage(0)


def main() -> None:
    """
    程序主函数。

    初始化流程：
    1. 设置 DPI 感知
    2. 注册信号处理器（Ctrl+C）
    3. 启动后台线程（自动跳过器、扫描器）
    4. 注册全局热键
    5. 进入 Windows 消息循环

    消息循环：
        - 使用 PeekMessage 非阻塞获取消息
        - 定期检查 _should_exit 标志，支持优雅退出
        - 处理热键消息并执行相应操作

    清理流程：
        - 停止所有后台线程
        - 注销全局热键
        - 记录退出日志

    热键功能：
        - I: 切换自动跳过对话（带音效提示）
        - O: 开始/中断基质扫描
        - P: 截取游戏窗口客户区
        - U: 识别 ROI 区域文本并输出结果
    """
    global _should_exit

    # 设置 DPI 感知，确保坐标准确
    set_dpi_awareness()

    # 注册信号处理器，支持 Ctrl+C 退出
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 启动后台线程
    skipper = AutoSkipper(
        skip_pos=skip_conversation_clicks,
        click_interval=skip_conversation_click_interval,
    )
    skipper.start()

    recognizer = Recognizer()
    scanner = EssenceScanner(recognizer)
    scanner.start()

    # 注册全局热键
    register_hotkeys()

    try:
        msg = wintypes.MSG()

        # Windows 消息循环
        while not _should_exit:
            # 使用非阻塞的 PeekMessage，允许定期检查退出标志
            # PM_REMOVE = 1 表示从队列中移除消息
            ret = windll.user32.PeekMessageW(byref(msg), 0, 0, 0, 1)

            if ret:
                # 收到消息
                if msg.message == win32con.WM_QUIT:
                    break

                if msg.message == win32con.WM_HOTKEY:
                    # 处理热键消息
                    hotkey_id = msg.wParam

                    if hotkey_id == HOTKEY_ID_TOGGLE_SKIP:
                        # I 键：切换自动跳过对话
                        hwnd = win32gui.GetForegroundWindow()
                        if is_supported_window(hwnd):
                            skipper.enabled = not skipper.enabled
                            if skipper.enabled:
                                play_sound(enable_sound_path)
                                logging.info("Skip Conversation Enabled")
                            else:
                                play_sound(disable_sound_path)
                                logging.info("Skip Conversation Disabled")

                    elif hotkey_id == HOTKEY_ID_SCAN:
                        # O 键：扫描基质图标
                        toggle_essence_scan(scanner)

                    elif hotkey_id == HOTKEY_ID_SCREENSHOT:
                        # P 键：截图
                        hwnd = win32gui.GetForegroundWindow()
                        if is_supported_window(hwnd):
                            try:
                                screenshot_client(hwnd)
                            except Exception as e:
                                logging.exception("Failed to take screenshot: %s", e)

                    elif hotkey_id == HOTKEY_ID_RECOGNIZE:
                        # U 键：单次识别
                        hwnd = win32gui.GetForegroundWindow()
                        if is_supported_window(hwnd):
                            # 先截取 ROI 区域
                            roi_img = capture_client_roi_np(hwnd, BONUS_ROI)
                            if roi_img is not None:
                                label, score = recognizer.recognize(roi_img)
                                if label:
                                    logging.info(
                                        f"Recognized: {label} (score={score:.3f})"
                                    )
                                else:
                                    best_str = (
                                        f"{score:.3f}"
                                        if isinstance(score, float)
                                        else "n/a"
                                    )
                                    logging.info(
                                        f"Recognized: UNKNOWN (best={best_str})"
                                    )
                            else:
                                logging.warning("Failed to capture ROI")

                # 转发消息
                windll.user32.TranslateMessage(byref(msg))
                windll.user32.DispatchMessageW(byref(msg))
            else:
                # 无消息时短暂休眠，避免 CPU 占用过高
                time.sleep(0.01)

    except KeyboardInterrupt:
        logging.info("Exiting by user")
    finally:
        # 清理资源
        skipper.stop()
        scanner.stop()
        unregister_hotkeys()
        logging.info("Program terminated")


# ============================================================================
# 程序入口
# ============================================================================

if __name__ == "__main__":
    main()
