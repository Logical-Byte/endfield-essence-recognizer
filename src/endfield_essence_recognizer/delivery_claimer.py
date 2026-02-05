import importlib.resources
import threading
import time
import winsound
from typing import TYPE_CHECKING

import cv2

from endfield_essence_recognizer.core.layout.base import ResolutionProfile
from endfield_essence_recognizer.core.recognition.tasks.ui import UISceneLabel
from endfield_essence_recognizer.core.scanner.context import (
    ScannerContext,
)
from endfield_essence_recognizer.core.window import WindowManager
from endfield_essence_recognizer.utils.image import load_image
from endfield_essence_recognizer.utils.log import logger

if TYPE_CHECKING:
    from cv2.typing import MatLike


def check_scene(
    window_manager: WindowManager, ctx: ScannerContext, profile: ResolutionProfile
) -> bool:
    width, height = window_manager.get_client_size()
    if (width, height) != profile.RESOLUTION:
        logger.warning(
            f"检测到终末地窗口的客户区尺寸为 {width}x{height}，请将终末地分辨率调整为 {profile.RESOLUTION[0]}x{profile.RESOLUTION[1]} 窗口。"
        )
        return False

    screenshot = window_manager.screenshot(
        profile.LIST_OF_DELIVERY_JOBS_SCENE_CHECK_ROI
    )
    scene_label, _max_val = ctx.ui_scene_recognizer.recognize_roi_fallback(
        screenshot, fallback_label=UISceneLabel.UNKNOWN
    )
    if scene_label != UISceneLabel.LIST_OF_DELIVERY_JOBS:
        logger.warning("请切换至“地区建设 - 仓储节点 - 运送委托列表”界面。")
        return False
    return True


class DeliveryClaimer(threading.Thread):
    def __init__(
        self,
        ctx: ScannerContext,
        window_manager: WindowManager,
        profile: ResolutionProfile,
    ) -> None:
        super().__init__(daemon=True)
        self._running = threading.Event()
        self.ctx: ScannerContext = ctx
        self._window_manager: WindowManager = window_manager
        self._profile: ResolutionProfile = profile
        with (
            importlib.resources.files("endfield_essence_recognizer")
            / "templates/screenshot/武陵调度券_抢单界面.png"
        ).open("rb") as f:
            buffer = f.read()
            self._wuling_reward_template: MatLike = load_image(buffer)
        self._enable_sound_path = (
            importlib.resources.files("endfield_essence_recognizer")
            / "sounds/enable.wav"
        )

    def run(self) -> None:
        logger.info("开始抢单...")
        self._running.set()

        if not self._window_manager.target_exists:
            logger.info("未找到终末地窗口，停止抢单。")
            self._running.clear()
            return

        if self._window_manager.restore():
            time.sleep(0.5)

        if self._window_manager.activate():
            time.sleep(0.5)

        check_scene_result = check_scene(self._window_manager, self.ctx, self._profile)
        if not check_scene_result:
            self._running.clear()
            return

        while True:
            if not self._window_manager.target_is_active:
                logger.info("终末地窗口不在前台，停止抢单。")
                self._running.clear()
                break

            if not self._running.is_set():
                logger.info("抢单被中断。")
                break

            screenshot = self._window_manager.screenshot(
                self._profile.DELIVERY_JOB_REWARD_ROI
            )
            res = cv2.matchTemplate(
                screenshot, self._wuling_reward_template, cv2.TM_CCOEFF_NORMED
            )
            _, max_val, _, _ = cv2.minMaxLoc(res)
            if max_val >= 0.8:
                with importlib.resources.as_file(
                    self._enable_sound_path
                ) as enable_sound_path_ensured:
                    winsound.PlaySound(
                        str(enable_sound_path_ensured),
                        winsound.SND_FILENAME | winsound.SND_ASYNC,
                    )
                break
            else:
                logger.info("未检测到武陵调度券，继续抢单...")
                time.sleep(4)
                self._window_manager.click(1745, 1003)
                time.sleep(2)

    def stop(self) -> None:
        logger.info("停止基质扫描线程...")
        self._running.clear()
