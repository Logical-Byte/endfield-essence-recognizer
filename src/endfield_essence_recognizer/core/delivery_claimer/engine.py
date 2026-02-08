from __future__ import annotations

from typing import TYPE_CHECKING

from endfield_essence_recognizer.core.interfaces import (
    AutomationEngine,
    ImageSource,
    WindowActions,
)
from endfield_essence_recognizer.core.recognition.tasks.delivery_job_reward import (
    DeliveryJobRewardLabel,
)
from endfield_essence_recognizer.core.recognition.tasks.delivery_ui import (
    DeliverySceneLabel,
)
from endfield_essence_recognizer.utils.log import logger

if TYPE_CHECKING:
    import threading

    from endfield_essence_recognizer.core.layout.base import ResolutionProfile
    from endfield_essence_recognizer.core.recognition.recognizer import Recognizer
    from endfield_essence_recognizer.services.audio_service import AudioService


class DeliveryClaimerEngine(AutomationEngine):
    """
    Engine to automate the claiming of Wuling Dispatch Tickets.
    """

    def __init__(
        self,
        image_source: ImageSource,
        window_actions: WindowActions,
        profile: ResolutionProfile,
        delivery_scene_recognizer: Recognizer[DeliverySceneLabel],
        delivery_job_reward_recognizer: Recognizer[DeliveryJobRewardLabel],
        audio_service: AudioService,
        time_after_refresh: float = 3.0,
        time_after_recognition: float = 2.5,
    ) -> None:
        self._image_source = image_source
        self._window_actions = window_actions
        self._profile = profile
        self._delivery_scene_recognizer = delivery_scene_recognizer
        self._delivery_job_reward_recognizer = delivery_job_reward_recognizer
        self._audio_service = audio_service

        self._time_after_refresh = time_after_refresh
        self._time_after_recognition = time_after_recognition

    def execute(self, stop_event: threading.Event) -> None:
        """
        Execute the delivery claiming loop.
        """
        logger.debug("Starting DeliveryClaimerEngine execution.")
        self._execute(stop_event)
        logger.debug("DeliveryClaimerEngine execution finished.")

    def _check_window_and_scene(self) -> bool:
        if not self._window_actions.target_is_active:
            logger.info("终末地窗口不在前台，停止抢单。")
            return False
        if not self._check_scene():
            logger.warning("窗口检查或场景检查失败，停止抢单。")
            return False
        return True

    def _execute(self, stop_event: threading.Event) -> None:
        """
        Execute the delivery claiming loop.
        """
        logger.info("开始抢单...")

        if self._window_actions.restore():
            self._window_actions.wait(0.5)
        if self._window_actions.show():
            self._window_actions.wait(0.5)
        if self._window_actions.activate():
            self._window_actions.wait(0.5)

        logger.debug("开始抢单循环...")
        while not stop_event.is_set():
            logger.debug("Start of delivery claiming loop iteration.")

            if not self._check_window_and_scene():
                break

            # 3. Scan
            label = self._scan_for_reward()

            # 4. If Found
            if label == DeliveryJobRewardLabel.WULING_DISPATCH_TICKET:
                logger.success("已找到武陵调度券！抢单成功。")
                self._audio_service.play_enable()
                return  # User takes over

            # 5. If Not Found
            logger.info("未检测到武陵调度券，正在刷新...")
            self._window_actions.wait(self._time_after_recognition)
            if stop_event.is_set():
                break
            if not self._check_window_and_scene():
                break
            refresh_point = self._profile.DELIVERY_JOB_REFRESH_BUTTON_POINT
            self._window_actions.click(refresh_point.x, refresh_point.y)
            self._window_actions.wait(self._time_after_refresh)

        logger.info("抢单引擎已停止。")

    def _check_scene(self) -> bool:
        """
        Verify that we are in the correct scene.

        Logs warnings if:
        -   The window resolution does not match the profile.
        -   The current scene is not the delivery jobs list.
        """
        client_size = self._image_source.get_client_size()
        if client_size != self._profile.RESOLUTION:
            logger.warning(
                f"窗口分辨率 {client_size} 与配置 {self._profile.RESOLUTION} 不符。"
            )
            return False

        screenshot = self._image_source.screenshot(
            self._profile.LIST_OF_DELIVERY_JOBS_SCENE_CHECK_ROI
        )
        label, conf = self._delivery_scene_recognizer.recognize_roi_fallback(
            screenshot, fallback_label=DeliverySceneLabel.UNKNOWN
        )

        if label != DeliverySceneLabel.LIST_OF_DELIVERY_JOBS:
            logger.warning(
                f"不在运送委托列表界面。检测到: {label} ({conf:.2f})。 "
                "请切换至“地区建设 - 仓储节点 - 运送委托列表”界面。"
            )
            return False

        return True

    def _scan_for_reward(self) -> DeliveryJobRewardLabel:
        screenshot = self._image_source.screenshot(
            self._profile.DELIVERY_JOB_REWARD_ROI
        )
        label, _conf = self._delivery_job_reward_recognizer.recognize_roi_fallback(
            screenshot, fallback_label=DeliveryJobRewardLabel.UNKNOWN
        )
        return label
