import logging
import time
import winsound
from datetime import datetime
from pathlib import Path
from typing import Never

import pyautogui
import pygetwindow
import pynput
import win32gui

logging.basicConfig(
    level=logging.DEBUG,
    format="{asctime}.{msecs:03.0f} [{levelname}] {module}:{funcName}:{lineno} | {message}",
    datefmt="%Y-%m-%d %H:%M:%S",
    style="{",
)

enable_sound_path: Path = Path(__file__).parent / "sound/enable.wav"
disable_sound_path: Path = Path(__file__).parent / "sound/disable.wav"
screenshots_dir: Path = Path(__file__).parent / "screenshots"

supported_window_titles: list[str] = ["EndfieldTBeta2"]

skip_conversation_clicks: tuple[float, float] = (0.7160, 0.7444)
skip_conversation_key_code = pynput.keyboard.KeyCode(char="p")
skip_conversation_click_interval: float = 0.1  # 单位秒


enhance_aritifact_clicks: list[tuple[float, float]] = [
    (241 / 3268, 433 / 1892),
    (2973 / 3268, 1377 / 1892),
    (2953 / 3268, 1787 / 1892),
    (244 / 3268, 302 / 1892),
]
enhance_aritifact_key_code = pynput.keyboard.KeyCode(char="[")

screenshot_key_code = pynput.keyboard.KeyCode(char="]")


def _get_client_rect_of_window(window: pygetwindow.Window) -> tuple[int, int, int, int]:
    """Return client-area rect (left, top, width, height) in screen coords.
    Falls back to outer rect if handle not available.
    """
    hwnd = getattr(window, "_hWnd", None)
    print(hwnd)
    if not hwnd:
        return window.left, window.top, window.width, window.height
    # Client rect is (0,0,right,bottom) relative to client; convert to screen
    left, top = win32gui.ClientToScreen(hwnd, (0, 0))
    cr = win32gui.GetClientRect(hwnd)
    right, bottom = win32gui.ClientToScreen(hwnd, (cr[2], cr[3]))
    width = right - left
    height = bottom - top
    return left, top, width, height


def main() -> Never:
    def on_press(key) -> None:
        nonlocal on
        if key == skip_conversation_key_code:
            window = pygetwindow.getActiveWindow()
            if window is not None and window.title in supported_window_titles:
                on = not on
                if on:
                    winsound.PlaySound(str(enable_sound_path), flags=1)
                    logging.info("Skip Conversation Enabled")
                else:
                    winsound.PlaySound(str(disable_sound_path), flags=1)
                    logging.info("Skip Conversation Disabled")
        if key == enhance_aritifact_key_code:
            window = pygetwindow.getActiveWindow()
            if window is not None and window.title in supported_window_titles:
                logging.info("Enhance Aritifact")
                cleft, ctop, cwidth, cheight = _get_client_rect_of_window(window)
                for mx, my in enhance_aritifact_clicks:
                    x: int = round(cleft + mx * cwidth)
                    y: int = round(ctop + my * cheight)
                    # pyautogui.moveTo(x, y)
                    pyautogui.leftClick(x, y)
                    # time.sleep(0.1)
        if key == screenshot_key_code:
            window = pygetwindow.getActiveWindow()
            if window is not None and window.title in supported_window_titles:
                try:
                    left, top, width, height = _get_client_rect_of_window(window)
                    screenshots_dir.mkdir(parents=True, exist_ok=True)
                    ts = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
                    filename = screenshots_dir / f"screenshot-{ts}.png"
                    image = pyautogui.screenshot(region=(left, top, width, height))
                    image.save(filename)
                    logging.info(f"Screenshot (client area) saved: {filename}")
                except Exception as e:
                    logging.exception("Failed to take screenshot: %s", e)

    on: bool = False
    listener = pynput.keyboard.Listener(on_press=on_press)
    listener.start()
    while True:
        if on:
            window = pygetwindow.getActiveWindow()
            if window is not None and window.title in supported_window_titles:
                mx, my = skip_conversation_clicks
                cleft, ctop, cwidth, cheight = _get_client_rect_of_window(window)
                x: int = round(cleft + mx * cwidth)
                y: int = round(ctop + my * cheight)
                # pyautogui.moveTo(x, y)
                pyautogui.leftClick(x, y)
        time.sleep(skip_conversation_click_interval)


if __name__ == "__main__":
    main()
