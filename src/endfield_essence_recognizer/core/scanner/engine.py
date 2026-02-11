import itertools
import random
import shutil
import threading
import time
from typing import TYPE_CHECKING

import cv2
import numpy as np
from cv2.typing import MatLike

from endfield_essence_recognizer.core.interfaces import ImageSource, WindowActions
from endfield_essence_recognizer.core.layout.base import Region, ResolutionProfile
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
from endfield_essence_recognizer.models.user_setting import UserSetting
from endfield_essence_recognizer.services.user_setting_manager import UserSettingManager
from endfield_essence_recognizer.utils.image import resize_to_ref_roi
from endfield_essence_recognizer.utils.log import logger

if TYPE_CHECKING:
    from pathlib import Path

# 模板均为 1080p，高分辨率下 ROI 截图需缩放到此尺寸再送入识别器
_REF_PROFILE = Resolution1080p()


def images_similar(img1: MatLike, img2: MatLike, threshold: float = 20.0) -> bool:
    """
    比较两张图片是否足够相似（像素级）。

    使用 cv2.absdiff 计算逐像素差异，再用 np.mean 求平均差值。
    当平均差值低于阈值时认为两张图片相似。

    Args:
        img1: 第一张图片。
        img2: 第二张图片。
        threshold: 相似度阈值，越小越严格。默认 5.0。

    Returns:
        True 表示两张图片相似。
    """
    if img1.shape != img2.shape:
        return False
    diff = cv2.absdiff(img1, img2)
    return float(np.mean(diff)) < threshold


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
    from endfield_essence_recognizer.game_data.weapon import (
        get_gem_tag_name,
    )

    recognize_start = time.monotonic()

    stats: list[str | None] = []
    levels: list[int | None] = []

    # 截取客户区全局截图用于等级检测和子区域裁剪
    t0 = time.monotonic()
    mem_source = InMemoryImageSource.cache_from(image_source)
    full_screenshot = mem_source.screenshot()
    screenshot_time = time.monotonic() - t0

    rois = [profile.STATS_0_ROI, profile.STATS_1_ROI, profile.STATS_2_ROI]
    ref_rois = [
        _REF_PROFILE.STATS_0_ROI,
        _REF_PROFILE.STATS_1_ROI,
        _REF_PROFILE.STATS_2_ROI,
    ]

    t0 = time.monotonic()
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
    attr_time = time.monotonic() - t0

    t0 = time.monotonic()
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
    status_time = time.monotonic() - t0

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

    recognize_total = time.monotonic() - recognize_start
    logger.opt(colors=True).info(
        f"已识别当前基质，属性: <magenta>{stats_name}</>, <magenta>{abandon_label.value}</>, <magenta>{locked_label.value}</>"
    )
    logger.debug(
        f"recognize_essence 耗时: 总计={recognize_total:.3f}s "
        f"(截图={screenshot_time:.3f}s, 属性={attr_time:.3f}s, 状态={status_time:.3f}s)"
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

    # 图标点击随机偏移半径（像素），保持在图标区域内
    CLICK_RANDOM_RADIUS: int = 50

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
        self._last_click_pos: tuple[int, int] | None = None

        # 每个格子的截图计数，在每个格子开始时重置
        self._cell_screenshot_count: int = 0

        # DEV_MODE 下保存第一个格子的所有截图
        self._debug_first_cell_pending: bool = self._is_dev_mode()
        self._debug_dir: Path | None = None
        self._debug_step: int = 0

        from endfield_essence_recognizer.utils.log import str_properties_and_attrs

        logger.opt(lazy=True).debug(
            "Scanner profile configuration: {}",
            lambda: str_properties_and_attrs(profile),
        )

    @staticmethod
    def _is_dev_mode() -> bool:
        try:
            from endfield_essence_recognizer.core.config import get_server_config

            return get_server_config().dev_mode
        except Exception:
            return False

    def _debug_init_dir(self, cell_label: str) -> None:
        """为第一个格子的截图调试创建输出目录。"""
        from endfield_essence_recognizer.core.path import get_logs_dir

        self._debug_dir = get_logs_dir() / "debug_first_cell"
        if self._debug_dir.exists():
            shutil.rmtree(self._debug_dir)
        self._debug_dir.mkdir(parents=True, exist_ok=True)
        self._debug_step = 0
        logger.debug(f"DEV_MODE: 将保存 {cell_label} 扫描截图到 {self._debug_dir}")

    def _debug_save(self, image: MatLike, label: str) -> None:
        """DEV_MODE 下保存一张调试截图（仅第一个格子生效）。"""
        if self._debug_dir is None:
            return
        filename = f"{self._debug_step:03d}_{label}.png"
        path = self._debug_dir / filename
        cv2.imwrite(str(path), image)
        self._debug_step += 1

    def _random_click_pos(
        self, center_x: int, center_y: int, radius: int | None = None
    ) -> tuple[int, int]:
        """
        在图标中心附近生成随机点击坐标，确保与上一次点击位置不同。

        通过每次点击位置不同，使鼠标光标在截图中的位置发生变化，
        帮助 _wait_until_stable 检测到画面变动。

        Args:
            center_x: 图标中心 X 坐标。
            center_y: 图标中心 Y 坐标。
            radius: 随机偏移半径（像素），默认使用 CLICK_RANDOM_RADIUS。

        Returns:
            (x, y) 随机偏移后的点击坐标。
        """
        if radius is None:
            radius = self.CLICK_RANDOM_RADIUS
        while True:
            x = center_x + random.randint(-radius, radius)
            y = center_y + random.randint(-radius, radius)
            if (x, y) != self._last_click_pos:
                self._last_click_pos = (x, y)
                return x, y

    def _wait_until_stable(
        self,
        roi: Region,
        before_image: MatLike,
        *,
        timeout: float = 2.0,
        poll_interval: float = 0.05,
        similarity_threshold: float = 5.0,
        no_change_timeout: float = 0.5,
    ) -> bool:
        """
        截图轮询等待：等待指定 ROI 区域发生变化并稳定下来。

        先检测画面变动（与 before_image 不同），再检测画面稳定（连续两帧相似）

        如果持续 no_change_timeout 秒未检测到任何变化（例如点击的是已选中的图标），
        则提前退出，避免等满完整的 timeout。

        Args:
            roi: 要监测的屏幕区域。
            before_image: 点击前该 ROI 的截图，用于检测"是否已变化"。
            timeout: 最长等待时间（秒）。超时后静默返回，扫描继续。
            poll_interval: 轮询间隔（秒）。
            similarity_threshold: 图像相似度阈值，越小越严格。
            no_change_timeout: 持续未检测到变化时的快速退出时间（秒）。

        Returns:
            True 表示检测到变化并已稳定，False 表示超时。
        """
        start = time.monotonic()
        last_image: MatLike | None = None
        iterations = 0
        ever_changed = False

        while time.monotonic() - start < timeout:
            current = self._image_source.screenshot(roi)
            self._cell_screenshot_count += 1
            self._debug_save(current, f"wait_poll_{iterations + 1:03d}")

            diff = cv2.absdiff(before_image, current)
            mean_diff = float(np.mean(diff))
            changed = mean_diff >= similarity_threshold
            iterations += 1

            if changed:
                ever_changed = True
                if last_image is not None:
                    stab_diff = float(np.mean(cv2.absdiff(last_image, current)))
                    stable = stab_diff < similarity_threshold
                    if stable:
                        elapsed = time.monotonic() - start
                        logger.debug(
                            f"_wait_until_stable: 变化已稳定, "
                            f"耗时={elapsed:.3f}s, 轮询={iterations}次, "
                            f"vs_before_diff={mean_diff:.2f}, vs_last_diff={stab_diff:.2f}"
                        )
                        return True
            elif not ever_changed:
                # 如果从未检测到变化，且已超过 no_change_timeout，提前退出
                elapsed = time.monotonic() - start
                if elapsed >= no_change_timeout:
                    logger.debug(
                        f"_wait_until_stable: 无变化快速退出, "
                        f"耗时={elapsed:.3f}s, 轮询={iterations}次, "
                        f"mean_diff={mean_diff:.2f}"
                    )
                    return False

            last_image = current
            self._window_actions.wait(poll_interval)

        elapsed = time.monotonic() - start
        logger.debug(
            f"_wait_until_stable: 超时, "
            f"耗时={elapsed:.3f}s, 轮询={iterations}次, "
            f"ever_changed={ever_changed}"
        )
        return False

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

            cell_label = f"[{i + 1},{j + 1}]"
            logger.info(f"正在扫描第 {i + 1} 行第 {j + 1} 列的基质...")
            cell_start = time.monotonic()
            self._cell_screenshot_count = 0

            # DEV_MODE: 为第一个格子初始化截图保存目录
            if self._debug_first_cell_pending:
                self._debug_init_dir(cell_label)

            # 截取点击前的面板区域，用于变化检测
            before_img = self._image_source.screenshot(self._profile.AREA)
            self._cell_screenshot_count += 1
            self._debug_save(before_img, "before_area")

            # 点击基质图标位置（随机偏移，使鼠标位置与上次不同）
            click_x, click_y = self._random_click_pos(relative_x, relative_y)
            self._window_actions.click(click_x, click_y)

            # 截图轮询：等待右侧信息面板刷新并稳定
            t0 = time.monotonic()
            self._wait_until_stable(self._profile.AREA, before_img)
            wait_time = time.monotonic() - t0

            # 识别基质信息（内部截取 1 张全屏截图）
            t0 = time.monotonic()
            data = recognize_essence(
                self._image_source,
                self.ctx,
                self._profile,
            )
            self._cell_screenshot_count += 1  # recognize_essence 内部 cache_from
            recognize_time = time.monotonic() - t0

            if (
                data.abandon_label == AbandonStatusLabel.MAYBE_ABANDONED
                or data.lock_label == LockStatusLabel.MAYBE_LOCKED
            ):
                cell_total = time.monotonic() - cell_start
                logger.debug(
                    f"{cell_label} 耗时: 总计={cell_total:.3f}s "
                    f"(等待={wait_time:.3f}s, 识别={recognize_time:.3f}s) "
                    f"截图={self._cell_screenshot_count}次 [识别不确定, 跳过]"
                )
                # DEV_MODE: 第一个格子结束，关闭截图保存
                if self._debug_first_cell_pending:
                    self._debug_first_cell_pending = False
                    self._debug_dir = None
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
            action_time_total = 0.0
            for action in actions:
                # 根据 action 类型选择对应的按钮 ROI，截取点击前状态
                button_roi = (
                    self._profile.LOCK_BUTTON_ROI
                    if action.type == ActionType.CLICK_LOCK
                    else self._profile.DEPRECATE_BUTTON_ROI
                )
                before_img = self._image_source.screenshot(button_roi)
                self._cell_screenshot_count += 1
                action_label = (
                    "before_lock"
                    if action.type == ActionType.CLICK_LOCK
                    else "before_abandon"
                )
                self._debug_save(before_img, action_label)

                if action.type == ActionType.CLICK_LOCK:
                    pos = self._profile.LOCK_BUTTON_POS
                    self._window_actions.click(pos.x, pos.y)
                elif action.type == ActionType.CLICK_ABANDON:
                    pos = self._profile.DEPRECATE_BUTTON_POS
                    self._window_actions.click(pos.x, pos.y)

                # 截图轮询：等待按钮状态变化并稳定
                t0 = time.monotonic()
                self._wait_until_stable(button_roi, before_img)
                action_wait = time.monotonic() - t0
                action_time_total += action_wait
                logger.success(action.log_message)

            cell_total = time.monotonic() - cell_start
            logger.debug(
                f"{cell_label} 耗时: 总计={cell_total:.3f}s "
                f"(等待={wait_time:.3f}s, 识别={recognize_time:.3f}s"
                + (f", 动作={action_time_total:.3f}s" if actions else "")
                + f") 截图={self._cell_screenshot_count}次"
            )

            # DEV_MODE: 第一个格子结束，关闭截图保存
            if self._debug_first_cell_pending:
                logger.debug(
                    f"DEV_MODE: 第一个格子截图已保存到 {self._debug_dir}，"
                    f"共 {self._debug_step} 张"
                )
                self._debug_first_cell_pending = False
                self._debug_dir = None

        else:
            # 扫描完成
            logger.info("基质扫描完成。")
