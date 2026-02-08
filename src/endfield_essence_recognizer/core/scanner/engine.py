import itertools
import threading

from endfield_essence_recognizer.core.interfaces import ImageSource, WindowActions
from endfield_essence_recognizer.core.layout.base import ResolutionProfile
from endfield_essence_recognizer.core.recognition import (
    AbandonStatusLabel,
    LockStatusLabel,
)
from endfield_essence_recognizer.core.recognition.tasks.ui import UISceneLabel
from endfield_essence_recognizer.core.scanner.action_logic import (
    ActionType,
    decide_actions,
)
from endfield_essence_recognizer.core.scanner.context import (
    ScannerContext,
)
from endfield_essence_recognizer.core.scanner.evaluate import evaluate_essence
from endfield_essence_recognizer.core.scanner.models import (
    EssenceData,
    EssenceQuality,
)
from endfield_essence_recognizer.core.window.adapter import InMemoryImageSource
from endfield_essence_recognizer.models.user_setting import UserSetting
from endfield_essence_recognizer.services.user_setting_manager import UserSettingManager
from endfield_essence_recognizer.utils.log import logger


def check_scene(
    image_source: ImageSource, ctx: ScannerContext, profile: ResolutionProfile
) -> bool:
    width, height = image_source.get_client_size()
    if (width, height) != profile.RESOLUTION:
        logger.warning(
            f"检测到终末地窗口的客户区尺寸为 {width}x{height}，请将终末地分辨率调整为 {profile.RESOLUTION[0]}x{profile.RESOLUTION[1]} 窗口。"
        )
        return False

    screenshot = image_source.screenshot(profile.ESSENCE_UI_ROI)
    scene_label, _max_val = ctx.ui_scene_recognizer.recognize_roi_fallback(
        screenshot, fallback_label=UISceneLabel.UNKNOWN
    )
    if scene_label != UISceneLabel.ESSENCE_UI:
        logger.warning(
            '当前界面不是基质界面。请按 "N" 键打开贵重品库后切换到武器基质页面。'
        )
        return False
    return True


def recognize_essence(
    image_source: ImageSource,
    ctx: ScannerContext,
    profile: ResolutionProfile,
) -> EssenceData:
    from endfield_essence_recognizer.game_data.weapon import (
        get_gem_tag_name,
    )

    stats: list[str | None] = []
    levels: list[int | None] = []

    # 截取客户区全局截图用于等级检测和子区域裁剪
    mem_source = InMemoryImageSource.cache_from(image_source)
    full_screenshot = mem_source.screenshot()

    rois = [profile.STATS_0_ROI, profile.STATS_1_ROI, profile.STATS_2_ROI]

    for k, roi in enumerate(rois):
        screenshot_image = mem_source.screenshot(roi)
        attr, max_val = ctx.attr_recognizer.recognize_roi(screenshot_image)
        stats.append(attr)
        logger.debug(f"属性 {k} 识别结果: {attr} (分数: {max_val:.3f})")

        # 识别等级（通过检测坐标点状态）
        level_value = ctx.attr_level_recognizer.recognize_level(full_screenshot, k)
        levels.append(level_value)

        if level_value is not None:
            logger.debug(f"属性 {k} 等级识别结果: +{level_value}")
        else:
            logger.debug(f"属性 {k} 等级识别结果: 无法识别")

    screenshot_image = mem_source.screenshot(profile.DEPRECATE_BUTTON_ROI)
    abandon_label, max_val = ctx.abandon_status_recognizer.recognize_roi_fallback(
        screenshot_image,
        fallback_label=AbandonStatusLabel.MAYBE_ABANDONED,
    )
    logger.debug(f"弃用按钮识别结果: {abandon_label.value} (分数: {max_val:.3f})")

    screenshot_image = mem_source.screenshot(profile.LOCK_BUTTON_ROI)
    locked_label, max_val = ctx.lock_status_recognizer.recognize_roi_fallback(
        screenshot_image,
        fallback_label=LockStatusLabel.MAYBE_LOCKED,
    )
    logger.debug(f"锁定按钮识别结果: {locked_label.value} (分数: {max_val:.3f})")

    stats_name_parts = []
    for i, stat in enumerate(stats):
        if stat is None:
            stats_name_parts.append("无")
        else:
            stat_name = get_gem_tag_name(stat, "CN")
            if i < len(levels) and levels[i] is not None:
                stats_name_parts.append(f"{stat_name}+{levels[i]}")
            else:
                stats_name_parts.append(stat_name)
    stats_name = "、".join(stats_name_parts)

    logger.opt(colors=True).info(
        f"已识别当前基质，属性: <magenta>{stats_name}</>, <magenta>{abandon_label.value}</>, <magenta>{locked_label.value}</>"
    )

    return EssenceData(stats, levels, abandon_label, locked_label)


def recognize_once(
    image_source: ImageSource,
    ctx: ScannerContext,
    user_setting: UserSetting,
    profile: ResolutionProfile,
) -> None:
    mem_source = InMemoryImageSource.cache_from(image_source)

    check_scene_result = check_scene(mem_source, ctx, profile)
    if not check_scene_result:
        return

    data = recognize_essence(
        mem_source,
        ctx,
        profile,
    )

    if (
        data.abandon_label == AbandonStatusLabel.MAYBE_ABANDONED
        or data.lock_label == LockStatusLabel.MAYBE_LOCKED
    ):
        return

    evaluation = evaluate_essence(data, user_setting)
    # all logs use success for simplicity
    logger.opt(colors=True).success(evaluation.log_message)


class ScannerEngine:
    """
    基质图标扫描器引擎。

    此引擎负责自动遍历游戏界面中的 45 个基质图标位置，
    对每个位置执行"点击 -> 截图 -> 识别"的流程。
    """

    def __init__(
        self,
        ctx: ScannerContext,
        image_source: ImageSource,
        window_actions: WindowActions,
        user_setting_manager: UserSettingManager,
        profile: ResolutionProfile,
    ) -> None:
        self.ctx: ScannerContext = ctx
        self._image_source = image_source
        self._window_actions = window_actions
        self._user_setting_manager: UserSettingManager = user_setting_manager
        self._profile: ResolutionProfile = profile

        from endfield_essence_recognizer.utils.log import str_properties_and_attrs

        logger.opt(lazy=True).debug(
            "Scanner profile configuration: {}",
            lambda: str_properties_and_attrs(profile),
        )

    def execute(self, stop_event: threading.Event) -> None:
        """
        Run the 9*5 grid scanning process with start/end logging.
        """
        logger.debug("ScannerEngine started execution.")
        self._execute_grid_scan(stop_event)
        logger.debug("ScannerEngine finished execution.")

    def _execute_grid_scan(self, stop_event: threading.Event) -> None:
        """
        Actual execution logic for a 9*5 grid pass.
        """
        if not self._window_actions.target_exists:
            logger.info("未找到终末地窗口，停止基质扫描。")
            return

        if self._window_actions.restore():
            self._window_actions.wait(0.5)

        if self._window_actions.activate():
            self._window_actions.wait(0.5)

        if self._window_actions.show():
            # make the window visible in the beginning
            self._window_actions.wait(0.5)

        logger.debug("Made the window visible and active.")

        check_scene_result = check_scene(self._image_source, self.ctx, self._profile)
        if not check_scene_result:
            return

        # 获取当前用户设置的快照，用于接下来的判断
        user_setting = self._user_setting_manager.get_user_setting()

        icon_x_list = self._profile.essence_icon_x_list
        icon_y_list = self._profile.essence_icon_y_list

        for (i, relative_y), (j, relative_x) in itertools.product(
            enumerate(icon_y_list), enumerate(icon_x_list)
        ):
            if not self._window_actions.target_is_active:
                logger.info("终末地窗口不在前台，停止基质扫描。")
                break

            if stop_event.is_set():
                logger.info("基质扫描被中断。")
                break

            logger.info(f"正在扫描第 {i + 1} 行第 {j + 1} 列的基质...")

            # 点击基质图标位置
            self._window_actions.click(relative_x, relative_y)

            # 等待短暂时间以确保界面更新
            self._window_actions.wait(0.3)

            # 识别基质信息
            data = recognize_essence(
                self._image_source,
                self.ctx,
                self._profile,
            )

            if (
                data.abandon_label == AbandonStatusLabel.MAYBE_ABANDONED
                or data.lock_label == LockStatusLabel.MAYBE_LOCKED
            ):
                # early continue on uncertain recognition
                continue

            evaluation = evaluate_essence(data, user_setting)

            # Log the result
            if (
                evaluation.quality == EssenceQuality.TRASH
                and evaluation.matched_weapons
            ):
                logger.opt(colors=True).warning(evaluation.log_message)
            else:
                logger.opt(colors=True).success(evaluation.log_message)

            # Decide actions
            actions = decide_actions(data, evaluation, user_setting)

            # Execute actions
            for action in actions:
                if action.type == ActionType.CLICK_LOCK:
                    pos = self._profile.LOCK_BUTTON_POS
                    self._window_actions.click(pos.x, pos.y)
                elif action.type == ActionType.CLICK_ABANDON:
                    pos = self._profile.DEPRECATE_BUTTON_POS
                    self._window_actions.click(pos.x, pos.y)

                self._window_actions.wait(0.3)
                logger.success(action.log_message)

        else:
            # 扫描完成
            logger.info("基质扫描完成。")
