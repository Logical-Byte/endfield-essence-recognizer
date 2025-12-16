"""自动跳过对话线程模块。"""

import threading
import time

import win32gui


def is_supported_window(hwnd: int) -> bool:
    """检查窗口是否为支持的游戏窗口。"""
    try:
        title = win32gui.GetWindowText(hwnd)
        return title in ["EndfieldTBeta2"]
    except Exception:  # noqa: BLE001
        return False


def client_pos_from_ratio(hwnd: int, ratio_x: float, ratio_y: float) -> tuple[int, int]:
    """
    根据客户区的比例坐标计算屏幕坐标。

    参数：
        hwnd: 窗口句柄
        ratio_x: X 方向比例（0-1）
        ratio_y: Y 方向比例（0-1）

    返回：
        屏幕上的 (x, y) 坐标
    """
    from ctypes import byref, windll, wintypes

    rect = wintypes.RECT()
    windll.user32.GetClientRect(hwnd, byref(rect))
    width = rect.right - rect.left
    height = rect.bottom - rect.top

    point = wintypes.POINT(rect.left, rect.top)
    windll.user32.ClientToScreen(hwnd, byref(point))

    x = point.x + int(width * ratio_x)
    y = point.y + int(height * ratio_y)

    return x, y


def send_left_click(x: int, y: int) -> None:
    """在指定屏幕坐标执行左键单击。"""
    import win32api
    import win32con

    win32api.SetCursorPos((x, y))
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)


class AutoSkipper(threading.Thread):
    """
    自动跳过对话后台线程。

    此线程在启用时会以固定间隔在屏幕特定位置执行鼠标点击，
    用于自动跳过游戏中的对话和动画。

    属性：
        enabled: 功能是否启用
        _stop: 线程停止事件

    使用方法：
        skipper = AutoSkipper()
        skipper.start()  # 启动后台线程
        skipper.enabled = True  # 启用自动跳过
        skipper.enabled = False  # 禁用自动跳过
        skipper.stop()  # 停止线程
    """

    def __init__(
        self,
        skip_pos: tuple[float, float] = (0.7160, 0.7444),
        click_interval: float = 0.1,
    ) -> None:
        """
        初始化自动跳过器线程。

        参数：
            skip_pos: 点击位置的相对坐标（ratio_x, ratio_y），范围 0-1
            click_interval: 点击间隔，单位秒
        """
        super().__init__(daemon=True)
        self.enabled = False  # 功能启用标志
        self._stop = threading.Event()  # 线程停止信号
        self.skip_pos = skip_pos
        self.click_interval = click_interval

    def run(self) -> None:
        """
        线程主循环。

        持续检查 enabled 标志，当为 True 时：
        1. 获取前台窗口句柄
        2. 验证是否为支持的游戏窗口
        3. 在预设位置执行鼠标点击
        4. 等待指定间隔后重复

        注意：
            - 只有当前台窗口为游戏窗口时才会点击
            - 点击位置使用相对坐标，适应不同分辨率
        """
        while not self._stop.is_set():
            if self.enabled:
                # 获取前台窗口
                hwnd = win32gui.GetForegroundWindow()

                # 验证窗口
                if is_supported_window(hwnd):
                    # 计算点击位置的屏幕坐标
                    x, y = client_pos_from_ratio(hwnd, *self.skip_pos)
                    # 执行点击
                    send_left_click(x, y)

            # 等待下次点击间隔
            time.sleep(self.click_interval)
