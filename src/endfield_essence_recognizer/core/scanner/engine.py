import itertools
import threading

from endfield_essence_recognizer.core.interfaces import ImageSource, WindowActions
from endfield_essence_recognizer.core.layout.base import (
    Point,
    Region,
    ResolutionProfile,
)
from endfield_essence_recognizer.core.recognition import (
    AbandonStatusLabel,
    LockStatusLabel,
    RarityLabel,
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
from endfield_essence_recognizer.utils.log import logger


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
            f"与预期的 {profile.RESOLUTION[0]}x{profile.RESOLUTION[1]} 不一致；"
            f"请避免在运行时调整窗口大小。"
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
        level_value = ctx.attr_level_recognizer.recognize_level(
            full_screenshot, k, profile
        )
        levels.append(level_value)

        if level_value is not None:
            logger.debug(f"属性 {k} 等级识别结果: +{level_value}")
        else:
            logger.debug(f"属性 {k} 等级识别结果: 无法识别")

    # 识别稀有度（通过检测颜色）
    rarity_screenshot = mem_source.screenshot(profile.RARITY_ROI)
    rarity_label, score = ctx.rarity_recognizer.recognize_roi_fallback(
        rarity_screenshot, fallback_label=RarityLabel.OTHER
    )
    logger.debug(f"稀有度识别结果: {rarity_label.value} (分数: {score:.3f})")

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

    rarity_text = {
        RarityLabel.FIVE: "<yellow>无瑕</>",
        RarityLabel.FOUR: "<magenta>高纯</>",
        RarityLabel.OTHER: "其他",
    }.get(rarity_label, "未知")

    logger.opt(colors=True).info(
        f"已识别当前基质，属性: <magenta>{stats_name}</>, 稀有度: {rarity_text}, <magenta>{abandon_label.value}</>, <magenta>{locked_label.value}</>"
    )

    return EssenceData(stats, levels, rarity_label, abandon_label, locked_label)


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

        else:
            # 扫描完成
            logger.info("基质扫描完成。")


class DraggableScannerEngine(ScannerEngine):
    """
    支持拖拽翻页的基质扫描器引擎。

    继承自 ScannerEngine，添加了自动翻页功能：
    - 通过拖拽操作实现翻页
    - 检测滚动条位置判断是否到达底部
    - 支持翻页前后去重（避免重复扫描）
    """

    DEFAULT_DRAG_DURATION: float = 1.0
    """默认拖动持续时间（秒），减缓速度让游戏UI能跟上"""

    def _execute_grid_scan(self, stop_event: threading.Event) -> None:
        """
        执行带拖拽翻页的网格扫描。
        """
        if not self._window_actions.target_exists:
            logger.info("未找到终末地窗口，停止基质扫描。")
            return

        if self._window_actions.restore():
            self._window_actions.wait(0.5)

        if self._window_actions.activate():
            self._window_actions.wait(0.5)

        if self._window_actions.show():
            self._window_actions.wait(0.5)

        logger.debug("Made the window visible and active.")

        check_scene_result = check_scene(self._image_source, self.ctx, self._profile)
        if not check_scene_result:
            return

        # 获取当前用户设置的快照
        user_setting = self._user_setting_manager.get_user_setting()

        # 检查是否启用自动翻页
        auto_page_flip = user_setting.auto_page_flip
        if not auto_page_flip:
            logger.info("自动翻页已关闭，将只扫描当前页。")
            # 调用父类的单页扫描逻辑
            super()._execute_grid_scan(stop_event)
            return

        icon_x_list = self._profile.essence_icon_x_list
        icon_y_list = self._profile.essence_icon_y_list

        # 获取拖动配置
        drag_start = getattr(self._profile, "DRAG_START_POS", None)
        drag_end = getattr(self._profile, "DRAG_END_POS", None)

        if drag_start is None or drag_end is None:
            logger.warning("当前分辨率配置不支持拖拽翻页，将只扫描当前页。")
            super()._execute_grid_scan(stop_event)
            return

        # 获取滚动条检测配置
        scrollbar_pos = getattr(self._profile, "SCROLLBAR_CHECK_POS", None)

        page_count = 0
        is_last_page = False
        max_pages = 100  # 最大页数限制，防止无限循环

        # 初始化渐进拖动相关变量
        progressive_drag_distance = 0
        max_drag_distance = (
            int((drag_end.x - drag_start.x) ** 2 + (drag_end.y - drag_start.y) ** 2)
            ** 0.5
        )
        total_rows = len(icon_y_list)

        # 获取缩放因子，将逻辑最大距离转换为物理最大距离
        scale_factor = self._get_scale_factor()
        physical_max_drag_distance = max_drag_distance / scale_factor

        while not stop_event.is_set() and page_count < max_pages:
            page_count += 1
            logger.info(f"开始扫描第 {page_count} 页基质...")

            # 确定当前页需要扫描的行范围
            if is_last_page and page_count > 1:
                # 最后一页：根据渐进滚动比例计算需要跳过的行数
                skip_rows = self._calculate_skip_rows(
                    progressive_drag_distance, physical_max_drag_distance, total_rows
                )
                start_row = min(skip_rows, total_rows - 1)
                logger.info(
                    f"最后一页：渐进滚动了 {progressive_drag_distance}px/最大 {physical_max_drag_distance:.0f}px，跳过前 {start_row} 行"
                )
            else:
                start_row = 0

            # 扫描当前页（从指定行开始）
            self._scan_current_page(
                stop_event,
                user_setting,
                icon_x_list,
                icon_y_list,
                start_row_index=start_row,
            )

            # 如果已经扫描完最后一页，停止扫描
            if is_last_page:
                logger.info("已扫描完最后一页，基质扫描完成。")
                break

            # 检查停止事件
            if stop_event.is_set():
                logger.info("基质扫描被中断，停止翻页操作。")
                break

            # 执行渐进式拖动翻页
            logger.info("开始渐进式拖动翻页...")
            progressive_drag_distance, is_last_page = self._progressive_drag(
                drag_start,
                drag_end,
                scrollbar_pos,
                stop_event,
                step=50,  # 每次拖动50像素
                max_drag=max_drag_distance,
            )

            if is_last_page:
                logger.info(
                    f"检测到滚动条到底，已渐进滚动 {progressive_drag_distance}px，下一页将是最后一页。"
                )

        if page_count >= max_pages:
            logger.info(f"已达到最大页数限制 ({max_pages})，扫描停止。")
        logger.info("基质扫描完成。")

    def _scan_current_page(
        self,
        stop_event: threading.Event,
        user_setting: UserSetting,
        icon_x_list: list[int],
        icon_y_list: list[int],
        start_row_index: int = 0,
    ) -> None:
        """
        扫描当前页的所有基质。

        Args:
            start_row_index: 开始扫描的行索引（0表示从第一行开始）
        """
        # 从指定行开始扫描
        rows_to_scan = list(enumerate(icon_y_list))[start_row_index:]

        for i, relative_y in rows_to_scan:
            for j, relative_x in enumerate(icon_x_list):
                if not self._window_actions.target_is_active:
                    logger.info("终末地窗口不在前台，停止基质扫描。")
                    return

                if stop_event.is_set():
                    logger.info("基质扫描被中断。")
                    return

                logger.info(f"正在扫描第 {i + 1} 行第 {j + 1} 列的基质...")

                # 点击基质图标位置
                self._window_actions.click(relative_x, relative_y)
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
                    continue

                evaluation = evaluate_essence(
                    data, user_setting, self.ctx.static_game_data
                )

                if (
                    evaluation.quality == EssenceQuality.TRASH
                    and evaluation.matched_weapons
                ):
                    logger.opt(colors=True).warning(evaluation.log_message)
                else:
                    logger.opt(colors=True).success(evaluation.log_message)

                actions = decide_actions(data, evaluation, user_setting)

                for action in actions:
                    if action.type == ActionType.CLICK_LOCK:
                        pos = self._profile.LOCK_BUTTON_POS
                        self._window_actions.click(pos.x, pos.y)
                    elif action.type == ActionType.CLICK_ABANDON:
                        pos = self._profile.DEPRECATE_BUTTON_POS
                        self._window_actions.click(pos.x, pos.y)

                    self._window_actions.wait(0.3)
                    logger.success(action.log_message)

    def _check_scrollbar_at_bottom(self, check_pos: Point) -> bool:
        """
        检测滚动条是否已到达底部。

        在像素区域内检测是否有亮点（RGB 都高于 100），
        如果检测到亮点则认为是滚动条，表明已到达底部。

        Args:
            check_pos: 检测位置（像素坐标）

        Returns:
            True 如果检测到滚动条（已到达底部），False 否则
        """
        try:
            # 根据分辨率计算搜索半径（1080p 为 2，其他分辨率按比例缩放）
            resolution = self._profile.RESOLUTION
            scale_factor = resolution[1] / 1080
            radius = max(1, round(2 * scale_factor))

            # 截取检测位置附近的区域
            roi = Region(
                Point(check_pos.x - radius, check_pos.y - radius),
                Point(check_pos.x + radius + 1, check_pos.y + radius + 1),
            )
            screenshot = self._image_source.screenshot(roi)

            # 在区域内查找是否有亮点（RGB 都高于 100）
            height, width = screenshot.shape[:2]
            for y in range(height):
                for x in range(width):
                    pixel = screenshot[y, x]
                    b, g, r = int(pixel[0]), int(pixel[1]), int(pixel[2])
                    if r > 100 and g > 100 and b > 100:
                        logger.info(
                            f"检测到滚动条亮点 at ({check_pos.x - radius + x}, {check_pos.y - radius + y}): RGB({r}, {g}, {b})"
                        )
                        return True

            logger.debug(f"未检测到滚动条亮点 at ({check_pos.x}, {check_pos.y})")
            return False

        except Exception as e:
            logger.warning(f"滚动条检测失败: {e}")
            return False

    def _progressive_drag(
        self,
        drag_start: Point,
        drag_end: Point,
        scrollbar_pos: Point | None,
        stop_event: threading.Event,
        step: int = 50,
        max_drag: int = 800,
    ) -> tuple[int, bool]:
        """
        渐进式拖动，鼠标按住不放，每拖动一步检测一次滚动条是否到底。

        实现方式参考 drag_on_window：使用 moveTo 移动鼠标，保持 mouseDown 状态。

        Args:
            drag_start: 拖动起始位置
            drag_end: 拖动终止位置（目标位置）
            scrollbar_pos: 滚动条检测位置
            stop_event: 停止事件
            step: 每次拖动的像素数
            max_drag: 最大拖动距离

        Returns:
            (actual_drag_distance, is_last_page) 实际拖动距离和是否是最后一页
        """
        import time

        import pyautogui

        # 获取缩放因子并计算物理坐标
        scale_factor = self._get_scale_factor()
        physical_start = self._to_physical(drag_start, scale_factor)
        physical_end = self._to_physical(drag_end, scale_factor)

        # 计算物理拖动参数
        total_dx = physical_end.x - physical_start.x
        total_dy = physical_end.y - physical_start.y
        total_distance = (total_dx**2 + total_dy**2) ** 0.5

        # 限制最大拖动距离
        if max_drag > 0 and total_distance > max_drag / scale_factor:
            scale = (max_drag / scale_factor) / total_distance
            total_dx *= scale
            total_dy *= scale
            total_distance = max_drag / scale_factor

        # 计算步数和每步拖动量
        physical_step = step / scale_factor
        steps = max(1, int(total_distance / physical_step))
        step_dx, step_dy = total_dx / steps, total_dy / steps
        step_distance = (step_dx**2 + step_dy**2) ** 0.5

        logger.info(
            f"渐进拖动: 物理距离 {total_distance:.0f}px, 缩放因子 {scale_factor:.4f}, "
            f"分 {steps} 步, 每步偏移 ({step_dx:.0f}, {step_dy:.0f})"
        )

        # 获取起点屏幕坐标
        screen_start_x, screen_start_y = self._get_drag_start_position(drag_start)

        # 移动到起点并按住鼠标
        pyautogui.moveTo(screen_start_x, screen_start_y)
        pyautogui.mouseDown()
        logger.info(
            f"鼠标按住不放，从 ({screen_start_x}, {screen_start_y}) 开始渐进拖动"
        )
        time.sleep(0.2)

        actual_drag_distance = 0
        try:
            for i in range(steps):
                if stop_event.is_set():
                    logger.info("渐进拖动被中断")
                    break

                # 计算并移动到当前步位置
                progress = (i + 1) / steps
                current_x = screen_start_x + int(total_dx * progress)
                current_y = screen_start_y + int(total_dy * progress)
                pyautogui.moveTo(current_x, current_y)

                actual_drag_distance += step_distance
                logger.debug(
                    f"步 {i + 1}/{steps}: 移动到 ({current_x}, {current_y}), 累计 {actual_drag_distance:.0f}px"
                )

                time.sleep(0.05)

                # 检测滚动条是否到底
                if scrollbar_pos and self._check_scrollbar_at_bottom(scrollbar_pos):
                    logger.info(
                        f"步 {i + 1}/{steps}: 检测到滚动条到底，已拖动 {actual_drag_distance:.0f}px"
                    )
                    return int(actual_drag_distance), True

            # 检测最终状态
            is_last_page = bool(
                scrollbar_pos and self._check_scrollbar_at_bottom(scrollbar_pos)
            )
            if is_last_page:
                logger.info(
                    f"全部拖动完成后检测到滚动条到底，总计拖动 {actual_drag_distance:.0f}px"
                )

            return int(actual_drag_distance), is_last_page

        finally:
            pyautogui.mouseUp()
            logger.info(
                f"鼠标释放，渐进拖动结束，实际拖动距离: {actual_drag_distance:.0f}px"
            )

    def _get_drag_start_position(self, drag_start: Point) -> tuple[int, int]:
        """
        获取拖动起始位置的屏幕坐标。

        Args:
            drag_start: 逻辑坐标

        Returns:
            (screen_x, screen_y) 屏幕坐标
        """
        import pyautogui

        from endfield_essence_recognizer.core.window.windows_utils import (
            _get_client_rect,
        )

        window = self._get_window()
        if window is None:
            logger.warning("无法获取窗口对象，使用当前鼠标位置")
            return pyautogui.position()

        # 将逻辑坐标转换为物理坐标
        physical = self._to_physical(drag_start, self._get_scale_factor())

        # 计算屏幕坐标
        (left, top), _ = _get_client_rect(window)
        return left + physical.x, top + physical.y

    def _get_scale_factor(self) -> float:
        """获取缩放因子，默认为1.0。"""
        factor = getattr(self._window_actions, "scale_factor", None)
        return factor if factor is not None and factor > 0 else 1.0

    def _get_window(self):
        """获取窗口对象（支持嵌套包装器）。"""
        from endfield_essence_recognizer.core.window.manager import WindowManager

        actions = self._window_actions
        for _ in range(5):
            if hasattr(actions, "_window_manager"):
                wm = actions._window_manager
                if isinstance(wm, WindowManager):
                    return wm._get_window()
            if hasattr(actions, "_actions"):
                actions = actions._actions
            else:
                break
        return None

    def _to_physical(self, point: Point, scale_factor: float) -> Point:
        """将逻辑坐标转换为物理坐标。"""
        if scale_factor == 1.0:
            return point
        return Point(round(point.x / scale_factor), round(point.y / scale_factor))

    def _calculate_skip_rows(
        self,
        actual_drag: int,
        max_drag: int,
        total_rows: int,
    ) -> int:
        """
        根据渐进滚动比例计算需要跳过的行数。

        Args:
            actual_drag: 实际滚动距离
            max_drag: 最大滚动距离（完整一页的距离）
            total_rows: 总行数

        Returns:
            需要跳过的行数
        """
        if max_drag <= 0 or actual_drag <= 0:
            return 0

        # 计算比例并四舍五入为跳过行数
        ratio = actual_drag / max_drag
        skip_rows = total_rows - round(ratio * total_rows)

        logger.info(
            f"计算跳过行数: 比例={ratio:.2f}, 实际滚动={actual_drag}px, 最大={max_drag}px, 跳过={skip_rows}行"
        )

        return skip_rows
