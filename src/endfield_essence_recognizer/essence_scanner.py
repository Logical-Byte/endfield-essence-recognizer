"""基质图标扫描器线程模块。"""

import logging
import threading
import time

import numpy as np
import win32gui

from src.endfield_essence_recognizer.capture import (
    capture_client_roi_np,
    get_client_rect_screen,
)
from src.endfield_essence_recognizer.recognizer import BONUS_ROI, Recognizer

# 基质图标位置网格（客户区像素坐标）
# 9列5行，共45个图标位置
essence_icon_x_list = np.linspace(128, 1374, 9).astype(int)
essence_icon_y_list = np.linspace(196, 819, 5).astype(int)
icon_pos_grid = np.array(
    [(x, y) for y in essence_icon_y_list for x in essence_icon_x_list]
)


def is_supported_window(hwnd: int) -> bool:
    """检查窗口是否为支持的游戏窗口。"""
    try:
        title = win32gui.GetWindowText(hwnd)
        return title in ["EndfieldTBeta2"]
    except Exception:  # noqa: BLE001
        return False


def send_left_click(x: int, y: int) -> None:
    """在指定屏幕坐标执行左键单击。"""
    import win32api
    import win32con

    win32api.SetCursorPos((x, y))
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)


def screenshot_client(hwnd: int) -> None:
    """截取游戏窗口客户区。"""
    from datetime import datetime
    from pathlib import Path

    import cv2
    import win32con
    import win32gui
    import win32ui

    _left, _top, width, height = get_client_rect_screen(hwnd)

    hdc = win32gui.GetDC(hwnd)
    mdc = win32ui.CreateDCFromHandle(hdc)
    save_dc = mdc.CreateCompatibleDC()

    save_bmp = win32ui.CreateBitmap()
    save_bmp.CreateCompatibleBitmap(mdc, width, height)
    save_dc.SelectObject(save_bmp)
    save_dc.BitBlt((0, 0), (width, height), mdc, (0, 0), win32con.SRCCOPY)

    # 转换为 numpy 数组
    bmp_str = save_bmp.GetBitmapBits(True)
    img_array = np.frombuffer(bmp_str, dtype=np.uint8).reshape(height, width, 4)
    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_BGRA2BGR)

    # 保存截图
    screenshots_dir = Path(__file__).parent / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filepath = screenshots_dir / f"screenshot_{timestamp}.png"
    save_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hdc)


class EssenceScanner(threading.Thread):
    """
    基质图标扫描器后台线程。

    此线程负责自动遍历游戏界面中的 45 个基质图标位置，
    对每个位置执行"点击 -> 截图 -> 识别"的流程。

    属性：
        scanning: 当前是否正在扫描
        _stop: 线程停止事件
        _interrupt: 扫描中断事件

    使用方法：
        scanner = EssenceScanner()
        scanner.start()  # 启动后台线程
        scanner.start_scan()  # 开始扫描
        scanner.start_scan()  # 再次调用会中断当前扫描
        scanner.stop()  # 停止线程
    """

    def __init__(self, recognizer: Recognizer) -> None:
        """初始化扫描器线程，设置为守护线程。"""
        super().__init__(daemon=True)
        self.recognizer = recognizer
        self.scanning = False  # 扫描状态标志
        self._stop = threading.Event()  # 线程停止信号
        self._interrupt = threading.Event()  # 扫描中断信号

    def run(self) -> None:
        """
        线程主循环。

        持续检查 scanning 标志，当为 True 时执行扫描流程：
        1. 获取前台窗口句柄并验证
        2. 遍历 icon_pos_grid 中的 45 个位置
        3. 对每个位置：
           - 点击图标
           - 等待界面更新（0.3秒）
           - 截取全屏（用于调试）
           - 识别 ROI 区域文本
           - 记录识别结果
        4. 扫描完成或被中断后重置状态

        注意：
            - 如果前台窗口不是游戏窗口，扫描会自动取消
            - 扫描过程中可以通过再次按 O 键中断
        """
        while not self._stop.is_set():
            if self.scanning:
                # 获取当前前台窗口
                hwnd = win32gui.GetForegroundWindow()

                # 验证窗口是否为支持的游戏窗口
                if is_supported_window(hwnd):
                    left, top, _width, _height = get_client_rect_screen(hwnd)
                    logging.info(
                        f"Starting essence scan: {len(icon_pos_grid)} positions"
                    )

                    # 遍历所有图标位置
                    for idx, (px, py) in enumerate(icon_pos_grid):
                        # 检查是否收到中断信号
                        if self._interrupt.is_set():
                            logging.info(
                                f"Scan interrupted at position {idx + 1} / {len(icon_pos_grid)}"  # noqa: E501
                            )
                            break

                        # 将客户区像素坐标转换为屏幕坐标
                        x = left + int(px)
                        y = top + int(py)

                        # 点击图标
                        send_left_click(x, y)
                        time.sleep(0.3)  # 等待点击生效和界面更新

                        # 截取全屏（用于离线调试分析）
                        try:
                            screenshot_client(hwnd)
                        except Exception as e:  # noqa: BLE001
                            logging.error(
                                f"Screenshot failed at position {idx + 1}: {e}"
                            )

                        # 截取 ROI 区域并识别属性文本
                        roi_img = capture_client_roi_np(hwnd, BONUS_ROI)
                        if roi_img is not None:
                            label, score = self.recognizer.recognize(roi_img)
                            if label:
                                log_msg = (
                                    f"[{idx + 1:02d}/{len(icon_pos_grid)}] "
                                    f"Recognized: {label} (score={score:.3f})"
                                )
                                logging.info(log_msg)
                            else:
                                # 未能识别
                                msg_score = (
                                    f"{score:.3f}"
                                    if isinstance(score, float)
                                    else "n/a"
                                )
                                log_msg = (
                                    f"[{idx + 1:02d}/{len(icon_pos_grid)}] "
                                    f"Recognized: UNKNOWN (best={msg_score})"
                                )
                                logging.info(log_msg)
                        else:
                            logging.warning(
                                f"[{idx + 1:02d}/{len(icon_pos_grid)}] "
                                f"Failed to capture ROI"
                            )

                        time.sleep(0.1)  # 点击间隔，避免操作过快

                    logging.info("Essence scan completed")
                    self.scanning = False
                    self._interrupt.clear()
                else:
                    # 前台窗口不是游戏窗口，取消扫描
                    self.scanning = False

            # 短暂休眠，避免空转占用 CPU
            time.sleep(0.1)

    def start_scan(self) -> None:
        """
        开始新的扫描或中断当前扫描。

        如果当前正在扫描，再次调用会触发中断；
        如果当前空闲，则开始新的扫描。

        这种设计允许用户通过反复按 O 键来控制扫描流程。
        """
        if self.scanning:
            # 正在扫描，触发中断
            logging.info("Interrupting current scan...")
            self._interrupt.set()
            self.scanning = False
        else:
            # 空闲状态，开始新的扫描
            self._interrupt.clear()
            self.scanning = True

    def stop(self) -> None:
        """
        停止扫描器线程。

        设置停止标志和中断标志，线程将在当前循环结束后退出。
        """
        self._stop.set()
        self._interrupt.set()
