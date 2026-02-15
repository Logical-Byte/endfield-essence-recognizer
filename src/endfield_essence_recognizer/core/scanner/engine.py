import itertools
import threading

from endfield_essence_recognizer.core.interfaces import ImageSource, WindowActions
from endfield_essence_recognizer.core.layout.base import Point, ResolutionProfile
from endfield_essence_recognizer.core.layout.res_1080p import Resolution1080p
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
from endfield_essence_recognizer.schemas.user_setting import UserSetting
from endfield_essence_recognizer.services.user_setting_manager import UserSettingManager
from endfield_essence_recognizer.utils.image import resize_to_ref_roi
from endfield_essence_recognizer.utils.log import logger

# 模板均为 1080p，高分辨率下 ROI 截图需缩放到此尺寸再送入识别器
_REF_PROFILE = Resolution1080p()


def check_scene(
    image_source: ImageSource, ctx: ScannerContext, profile: ResolutionProfile
) -> bool:
    width, height = image_source.get_client_size()
    if (width, height) != profile.RESOLUTION:
        # 运行过程中窗口被调整了大小（这应该比较少见）
        logger.debug(
            "Current window size: {}, profile expects: {}",
            (width, height),
            profile.RESOLUTION,
        )
        logger.warning(
            f"当前终末地窗口分辨率为 {width}x{height}，"
            f"请将游戏分辨率调整为 16:9 比例后重试（如 1920x1080、2560x1440、3840x2160 等）；避免在运行时调整窗口大小。"
        )
        return False

    screenshot = image_source.screenshot(profile.ESSENCE_UI_ROI)
    screenshot = resize_to_ref_roi(screenshot, _REF_PROFILE.ESSENCE_UI_ROI)
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
    stats: list[str | None] = []
    levels: list[int | None] = []

    # 截取客户区全局截图用于等级检测和子区域裁剪
    mem_source = InMemoryImageSource.cache_from(image_source)
    full_screenshot = mem_source.screenshot()

    rois = [profile.STATS_0_ROI, profile.STATS_1_ROI, profile.STATS_2_ROI]
    ref_rois = [
        _REF_PROFILE.STATS_0_ROI,
        _REF_PROFILE.STATS_1_ROI,
        _REF_PROFILE.STATS_2_ROI,
    ]

    for k, (roi, ref_roi) in enumerate(zip(rois, ref_rois, strict=True)):
        screenshot_image = mem_source.screenshot(roi)
        screenshot_image = resize_to_ref_roi(screenshot_image, ref_roi)
        attr, max_val = ctx.attr_recognizer.recognize_roi(screenshot_image)
        stats.append(attr)
        logger.debug(f"属性 {k} 识别结果: {attr} (分数: {max_val:.3f})")

        # 识别等级（通过检测坐标点状态）
        level_value = ctx.attr_level_recognizer.recognize_level(
            full_screenshot, k, profile
        )
        levels.append(level_value)

        if level_value is not None:
            logger.debug(f"属性 {k} 等级识别结果: +{level_value}")
        else:
            logger.debug(f"属性 {k} 等级识别结果: 无法识别")

    screenshot_image = mem_source.screenshot(profile.DEPRECATE_BUTTON_ROI)
    screenshot_image = resize_to_ref_roi(
        screenshot_image, _REF_PROFILE.DEPRECATE_BUTTON_ROI
    )
    abandon_label, max_val = ctx.abandon_status_recognizer.recognize_roi_fallback(
        screenshot_image,
        fallback_label=AbandonStatusLabel.MAYBE_ABANDONED,
    )
    logger.debug(f"弃用按钮识别结果: {abandon_label.value} (分数: {max_val:.3f})")

    screenshot_image = mem_source.screenshot(profile.LOCK_BUTTON_ROI)
    screenshot_image = resize_to_ref_roi(screenshot_image, _REF_PROFILE.LOCK_BUTTON_ROI)
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
            gem = ctx.static_game_data.get_stat(stat)
            if gem is not None:
                stat_name = gem.name
            else:
                # this should not happen
                logger.warning(f"无法在静态数据中找到基质 ID: {stat} 的名称")
                stat_name = stat
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

    evaluation = evaluate_essence(data, user_setting, ctx.static_game_data)
    # all logs use success for simplicity
    logger.opt(colors=True).success(evaluation.log_message)


class OneTimeRecognitionEngine:
    """
    单次基质识别引擎。

    此引擎执行一次性识别流程，包括窗口激活、场景检查、基质信息识别与评估；不会执行点击操作。
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

    def execute(self, stop_event: threading.Event) -> None:
        """
        执行单次识别流程。
        """
        if not self._window_actions.target_exists:
            logger.info("未找到终末地窗口，停止单次识别。")
            return

        if not self._window_actions.target_is_active:
            logger.debug("终末地窗口不在前台，尝试切换到前台以进行识别基质操作。")
            if self._window_actions.activate():
                self._window_actions.wait(0.3)
            if self._window_actions.show():
                # make sure the window is visible
                self._window_actions.wait(0.3)

        if stop_event.is_set():
            return

        user_setting = self._user_setting_manager.get_user_setting()
        recognize_once(
            self._image_source,
            self.ctx,
            user_setting,
            self._profile,
        )


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
        Actual execution logic for a 9*5 grid pass with drag scrolling support.
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

        # 获取拖动配置
        drag_start = self._profile.DRAG_START_POS
        drag_end = self._profile.DRAG_END_POS
        drag_duration = self._profile.DRAG_DURATION

        # 获取滚动条检测配置
        scrollbar_pos = self._profile.SCROLLBAR_CHECK_POS

        # 记录当前分辨率和缩放后的检测位置
        resolution = self._profile.RESOLUTION
        logger.info(f"当前分辨率: {resolution[0]}x{resolution[1]}, 滚动条检测位置: ({scrollbar_pos.x}, {scrollbar_pos.y})")

        # 检查是否启用自动翻页
        auto_page_flip = user_setting.auto_page_flip
        if not auto_page_flip:
            logger.info("自动翻页已关闭，将只扫描当前页。")

        page_count = 0
        is_last_page = False
        max_pages = 100 if auto_page_flip else 1  # 不自动翻页时只扫描1页

        while not stop_event.is_set() and page_count < max_pages:
            page_count += 1
            logger.info(f"开始扫描第 {page_count} 页基质...")

            for (i, relative_y), (j, relative_x) in itertools.product(
                enumerate(icon_y_list), enumerate(icon_x_list)
            ):
                if not self._window_actions.target_is_active:
                    logger.info("终末地窗口不在前台，停止基质扫描。")
                    return

                if stop_event.is_set():
                    logger.info("基质扫描被中断。")
                    return

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

                evaluation = evaluate_essence(data, user_setting, self.ctx.static_game_data)

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

            # 检测滚动条位置判断是否到达底部
            if not is_last_page and self._check_scrollbar_at_bottom(scrollbar_pos):
                logger.info("检测到滚动条已到达底部，再扫描一页后停止。")
                is_last_page = True

            # 如果已经扫描完最后一页，停止扫描
            if is_last_page:
                logger.info("已扫描最后一页，基质扫描完成。")
                break

            # 检查是否启用自动翻页，未启用则不执行翻页
            if not auto_page_flip:
                logger.info("自动翻页已关闭，扫描完成。")
                break

            # 执行拖动翻页操作（向上拖动）
            logger.info("正在拖动翻页到下一页...")
            self._window_actions.drag(
                drag_start.x, drag_start.y,
                drag_end.x, drag_end.y,
                duration=drag_duration
            )
            # 等待拖动动画完成（拖动1.0s + 保持0.3s + 等待0.2s + 额外等待让UI稳定）
            self._window_actions.wait(1.5)

        if page_count >= max_pages:
            logger.info(f"已达到最大页数限制 ({max_pages})，扫描停止。")
        logger.info("基质扫描完成。")

    def _check_scrollbar_at_bottom(
        self,
        check_pos: Point,
    ) -> bool:
        """
        检测滚动条是否已到达底部。

        在像素区域内检测是否有亮点（RGB 都高于 100），
        如果检测到亮点则认为是滚动条，表明已到达底部。
        搜索范围会根据分辨率自动缩放（1080p 为 5x5，其他分辨率按比例）。

        Args:
            check_pos: 检测位置（像素坐标）

        Returns:
            True 如果检测到滚动条（已到达底部），False 否则
        """
        try:
            # 根据分辨率计算搜索半径（1080p 为 2，其他分辨率按比例缩放）
            resolution = self._profile.RESOLUTION
            scale_factor = resolution[1] / 1080  # 基于高度缩放
            radius = max(1, round(2 * scale_factor))  # 至少为 1
            
            from endfield_essence_recognizer.core.layout.base import Region

            # 截取检测位置附近的区域
            roi = Region(
                Point(check_pos.x - radius, check_pos.y - radius),
                Point(check_pos.x + radius + 1, check_pos.y + radius + 1)
            )
            screenshot = self._image_source.screenshot(roi)

            # 在区域内查找是否有亮点（RGB 都高于 100）
            height, width = screenshot.shape[:2]
            for y in range(height):
                for x in range(width):
                    pixel = screenshot[y, x]
                    b, g, r = int(pixel[0]), int(pixel[1]), int(pixel[2])
                    # 如果 RGB 都高于 100，认为是亮点（滚动条）
                    if r > 100 and g > 100 and b > 100:
                        logger.info(f"检测到滚动条亮点 at ({check_pos.x - radius + x}, {check_pos.y - radius + y}): RGB({r}, {g}, {b})，搜索半径: {radius}")
                        return True

            logger.debug(f"未检测到滚动条亮点 at ({check_pos.x}, {check_pos.y})，搜索半径: {radius}")
            return False

        except Exception as e:
            logger.warning(f"滚动条检测失败: {e}")
            return False
