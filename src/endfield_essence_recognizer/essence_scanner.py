import importlib.resources
import threading
import time
from collections.abc import Sequence
from enum import StrEnum

import cv2
import numpy as np
from cv2.typing import MatLike

from endfield_essence_recognizer.core.layout.base import Point, ResolutionProfile
from endfield_essence_recognizer.core.recognition import (
    AbandonStatusLabel,
    AbandonStatusRecognizer,
    AttributeRecognizer,
    LockStatusLabel,
    LockStatusRecognizer,
)
from endfield_essence_recognizer.core.window import WindowManager
from endfield_essence_recognizer.game_data import (
    gem_table,
    get_translation,
    weapon_basic_table,
)
from endfield_essence_recognizer.game_data.item import get_item_name
from endfield_essence_recognizer.game_data.weapon import (
    get_gem_tag_name,
    weapon_stats_dict,
    weapon_type_int_to_translation_key,
)
from endfield_essence_recognizer.models.user_setting import Action, UserSetting
from endfield_essence_recognizer.services.user_setting_manager import UserSettingManager
from endfield_essence_recognizer.utils.image import load_image, to_gray_image
from endfield_essence_recognizer.utils.log import logger

# 识别相关常量
ESSENCE_UI_TEMPLATE_PATH = (
    importlib.resources.files("endfield_essence_recognizer")
    / "templates/screenshot/武器基质.png"
)


def detect_icon_state_at_point(image: MatLike, x: int, y: int, radius: int = 3) -> bool:
    """
    检测指定坐标点的图标状态。

    Args:
        image: 全局灰度图像（客户区截图）
        x: 图标中心 x 坐标（客户区像素坐标）
        y: 图标中心 y 坐标（客户区像素坐标）
        radius: 采样半径

    Returns:
        True 表示白色/亮色（激活），False 表示黑色/暗色（未激活）
    """
    height, width = image.shape[:2]
    if x < radius or x >= width - radius or y < radius or y >= height - radius:
        logger.warning(f"坐标点 ({x}, {y}) 超出图像范围")
        return False

    # 提取坐标点周围区域的平均亮度
    region = image[y - radius : y + radius + 1, x - radius : x + radius + 1]
    avg_brightness = np.mean(region)  # type: ignore

    # 阈值：大于 200 认为是白色/亮色（激活）
    is_active = avg_brightness > 200
    logger.trace(
        f"坐标点 ({x}, {y}) 亮度={avg_brightness:.1f}, 状态={'白色' if is_active else '灰色'}"
    )
    return is_active


def recognize_level_from_icon_points(
    image: MatLike,
    icon_points: Sequence[Point],
    radius: int = 2,
) -> int | None:
    """
    根据坐标点列表识别等级。

    Args:
        image: 全局图像（客户区截图）
        icon_points: 4个图标的坐标点列表 [Point(x1,y1), Point(x2,y2), Point(x3,y3), Point(x4,y4)]
        radius: 采样半径

    Returns:
        等级 (1-4) 或 None（识别失败）
    """
    gray = to_gray_image(image)

    # 检测每个图标的状态
    active_count = 0
    for i, p in enumerate(icon_points):
        is_active = detect_icon_state_at_point(gray, p.x, p.y, radius)
        logger.trace(
            f"图标 {i + 1} ({p.x},{p.y}) 状态: {'白色' if is_active else '灰色'}"
        )
        if is_active:
            active_count += 1
        else:
            # 假设白色图标是连续的，遇到黑色后不再计数
            break

    # 根据激活图标数量返回等级
    if 1 <= active_count <= 4:
        return active_count
    else:
        return None


def check_scene(window_manager: WindowManager, profile: ResolutionProfile) -> bool:
    width, height = window_manager.get_client_size()
    if (width, height) != profile.RESOLUTION:
        logger.warning(
            f"检测到终末地窗口的客户区尺寸为 {width}x{height}，请将终末地分辨率调整为 {profile.RESOLUTION[0]}x{profile.RESOLUTION[1]} 窗口。"
        )
        return False

    screenshot = window_manager.screenshot(profile.ESSENCE_UI_ROI)
    template = load_image(ESSENCE_UI_TEMPLATE_PATH.read_bytes())
    res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)
    logger.debug(f"基质界面模板匹配分数: {max_val:.3f}")
    if max_val < 0.8:
        logger.warning(
            '当前界面不是基质界面。请按 "N" 键打开贵重品库后切换到武器基质页面。'
        )
        return False
    return True


class EssenceQuality(StrEnum):
    TREASURE = "treasure"
    TRASH = "trash"


def judge_essence_quality(
    setting: UserSetting,
    stats: list[str | None],
    levels: list[int | None] | None = None,
) -> EssenceQuality:
    """根据识别到的属性判断基质品质，并输出日志提示。"""

    # 检查属性等级：如果启用了高等级判定，记录是否为高等级宝藏
    is_high_level_treasure = False
    high_level_info = ""
    if setting.high_level_treasure_enabled and levels is not None:
        for i, (stat, level) in enumerate(zip(stats, levels)):
            if (
                stat is not None
                and level is not None
                and level >= setting.high_level_treasure_threshold
            ):
                # 检查该词条是否为有效词条 (termType == 0/1/2，即基础属性、附加属性或技能属性)
                gem = gem_table.get(stat)
                if gem is not None and gem.get("termType") in (0, 1, 2):
                    is_high_level_treasure = True
                    high_level_info = (
                        f"（含高等级属性词条：{get_gem_tag_name(stat, 'CN')}+{level}）"
                    )
                    break

    # 尝试匹配用户自定义的宝藏基质条件
    for treasure_stat in setting.treasure_essence_stats:
        if (
            treasure_stat.attribute in stats
            and treasure_stat.secondary in stats
            and treasure_stat.skill in stats
        ):
            logger.opt(colors=True).success(
                f"这个基质是<green><bold><underline>宝藏</></></>，因为它符合你设定的宝藏基质条件{high_level_info}。"
            )
            return EssenceQuality.TREASURE

    # 尝试匹配已实装武器
    matched_weapon_ids: set[str] = set()
    for weapon_id in weapon_basic_table:
        weapon_stats = weapon_stats_dict[weapon_id]
        if (
            weapon_stats["attribute"] == stats[0]
            and weapon_stats["secondary"] == stats[1]
            and weapon_stats["skill"] == stats[2]
        ):
            matched_weapon_ids.add(weapon_id)

    if not matched_weapon_ids:
        # 未匹配到任何已实装武器
        if is_high_level_treasure:
            logger.opt(colors=True).success(
                f"这个基质是<green><bold><underline>宝藏</></></>，因为它有高等级属性词条{high_level_info}。"
                "<dim>（但不匹配任何已实装武器）</>"
            )
            return EssenceQuality.TREASURE
        else:
            logger.opt(colors=True).success(
                "这个基质是<red><bold><underline>养成材料</></></>，它不匹配任何已实装武器。"
            )
            return EssenceQuality.TRASH
    # 检查匹配到的武器中，是否有不在 trash_weapon_ids 中的
    non_trash_weapon_ids = matched_weapon_ids - set(setting.trash_weapon_ids)

    def format_weapon_description(weapon_id: str) -> str:
        """格式化武器描述，如`名称（稀有度★ 类型）`"""
        weapon_basic = weapon_basic_table[weapon_id]
        weapon_name = get_item_name(weapon_id, "CN")
        weapon_type = get_translation(
            weapon_type_int_to_translation_key[weapon_id], "CN"
        )
        return f"<bold>{weapon_name}（{weapon_basic['rarity']}★ {weapon_type}）</>"

    if non_trash_weapon_ids:
        # 只要有一个匹配武器未被拦截，就是宝藏

        # 输出所有匹配到且未被拦截的武器列表
        weapon_descriptions = [
            format_weapon_description(wid) for wid in non_trash_weapon_ids
        ]
        weapons_description_str = "、".join(weapon_descriptions)

        logger.opt(colors=True).success(
            f"这个基质是<green><bold><underline>宝藏</></></>，它完美契合武器{weapons_description_str}{high_level_info}。"
        )
        return EssenceQuality.TREASURE
    else:
        # 所有匹配到的武器都在 trash_weapon_ids 中

        # 输出所有匹配到的武器列表
        weapon_descriptions = [
            format_weapon_description(wid) for wid in matched_weapon_ids
        ]
        weapons_description_str = "、".join(weapon_descriptions)

        if is_high_level_treasure:
            logger.opt(colors=True).success(
                f"这个基质是<green><bold><underline>宝藏</></></>，因为它有高等级属性词条{high_level_info}。"
                f"<yellow>即使它匹配的所有武器{weapons_description_str}均已被用户手动拦截。</>"
            )
            return EssenceQuality.TREASURE
        else:
            logger.opt(colors=True).warning(
                f"这个基质虽然匹配武器{weapons_description_str}，但匹配的所有武器均已被用户手动拦截，"
                f"因此这个基质是<red><bold><underline>养成材料</></></>。"
            )
            return EssenceQuality.TRASH


def recognize_essence(
    window_manager: WindowManager,
    attr_recognizer: AttributeRecognizer,
    abandon_status_recognizer: AbandonStatusRecognizer,
    lock_status_recognizer: LockStatusRecognizer,
    profile: ResolutionProfile,
) -> tuple[list[str | None], list[int | None], AbandonStatusLabel, LockStatusLabel]:
    stats: list[str | None] = []
    levels: list[int | None] = []

    # 截取客户区全局截图用于等级检测
    full_screenshot = window_manager.screenshot()

    rois = [profile.STATS_0_ROI, profile.STATS_1_ROI, profile.STATS_2_ROI]
    level_icons = [
        profile.STATS_0_LEVEL_ICONS,
        profile.STATS_1_LEVEL_ICONS,
        profile.STATS_2_LEVEL_ICONS,
    ]

    for k, roi in enumerate(rois):
        screenshot_image = window_manager.screenshot(roi)
        attr, max_val = attr_recognizer.recognize_roi(screenshot_image)
        stats.append(attr)
        logger.debug(f"属性 {k} 识别结果: {attr} (分数: {max_val:.3f})")

        # 识别等级（通过检测坐标点状态）
        icon_points = level_icons[k]
        level_value = recognize_level_from_icon_points(
            full_screenshot, icon_points, profile.LEVEL_ICON_SAMPLE_RADIUS
        )
        levels.append(level_value)

        if level_value is not None:
            logger.debug(f"属性 {k} 等级识别结果: +{level_value}")
        else:
            logger.debug(f"属性 {k} 等级识别结果: 无法识别")

    screenshot_image = window_manager.screenshot(profile.DEPRECATE_BUTTON_ROI)
    abandon_label, max_val = abandon_status_recognizer.recognize_roi_fallback(
        screenshot_image,
        fallback_label=AbandonStatusLabel.MAYBE_ABANDONED,
    )
    logger.debug(f"弃用按钮识别结果: {abandon_label.value} (分数: {max_val:.3f})")

    screenshot_image = window_manager.screenshot(profile.LOCK_BUTTON_ROI)
    locked_label, max_val = lock_status_recognizer.recognize_roi_fallback(
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

    return stats, levels, abandon_label, locked_label


def recognize_once(
    window_manager: WindowManager,
    attr_recognizer: AttributeRecognizer,
    abandon_status_recognizer: AbandonStatusRecognizer,
    lock_status_recognizer: LockStatusRecognizer,
    user_setting: UserSetting,
    profile: ResolutionProfile,
) -> None:
    check_scene_result = check_scene(window_manager, profile)
    if not check_scene_result:
        return

    stats, levels, abandon_label, lock_label = recognize_essence(
        window_manager,
        attr_recognizer,
        abandon_status_recognizer,
        lock_status_recognizer,
        profile,
    )

    if (
        abandon_label == AbandonStatusLabel.MAYBE_ABANDONED
        or lock_label == LockStatusLabel.MAYBE_LOCKED
    ):
        return

    judge_essence_quality(user_setting, stats, levels)


class EssenceScanner(threading.Thread):
    """
    基质图标扫描器后台线程。

    此线程负责自动遍历游戏界面中的 45 个基质图标位置，
    对每个位置执行"点击 -> 截图 -> 识别"的流程。
    """

    def __init__(
        self,
        attr_recognizer: AttributeRecognizer,
        abandon_status_recognizer: AbandonStatusRecognizer,
        lock_status_recognizer: LockStatusRecognizer,
        window_manager: WindowManager,
        user_setting_manager: UserSettingManager,
        profile: ResolutionProfile,
    ) -> None:
        super().__init__(daemon=True)
        self._scanning = threading.Event()
        self._attr_recognizer: AttributeRecognizer = attr_recognizer
        self._abandon_status_recognizer: AbandonStatusRecognizer = (
            abandon_status_recognizer
        )
        self._lock_status_recognizer: LockStatusRecognizer = lock_status_recognizer
        self._window_manager: WindowManager = window_manager
        self._user_setting_manager: UserSettingManager = user_setting_manager
        self._profile: ResolutionProfile = profile

        from endfield_essence_recognizer.utils.log import str_properties_and_attrs

        logger.opt(lazy=True).debug(
            "Scanner profile configuration: {}",
            lambda: str_properties_and_attrs(profile),
        )

    def run(self) -> None:
        logger.info("开始基质扫描线程...")
        self._scanning.set()

        if not self._window_manager.target_exists:
            logger.info("未找到终末地窗口，停止基质扫描。")
            self._scanning.clear()
            return

        if self._window_manager.restore():
            time.sleep(0.5)

        if self._window_manager.activate():
            time.sleep(0.5)

        check_scene_result = check_scene(self._window_manager, self._profile)
        if not check_scene_result:
            self._scanning.clear()
            return

        # 获取当前用户设置的快照，用于接下来的判断
        user_setting = self._user_setting_manager.get_user_setting()

        icon_x_list = self._profile.essence_icon_x_list
        icon_y_list = self._profile.essence_icon_y_list

        for i, j in np.ndindex(len(icon_y_list), len(icon_x_list)):
            if not self._window_manager.target_is_active:
                logger.info("终末地窗口不在前台，停止基质扫描。")
                self._scanning.clear()
                break

            if not self._scanning.is_set():
                logger.info("基质扫描被中断。")
                break

            logger.info(f"正在扫描第 {i + 1} 行第 {j + 1} 列的基质...")

            # 点击基质图标位置
            relative_x = icon_x_list[j]
            relative_y = icon_y_list[i]
            self._window_manager.click(relative_x, relative_y)

            # 等待短暂时间以确保界面更新
            time.sleep(0.3)

            # 识别基质信息
            stats, levels, abandon_label, lock_label = recognize_essence(
                self._window_manager,
                self._attr_recognizer,
                self._abandon_status_recognizer,
                self._lock_status_recognizer,
                self._profile,
            )

            essence_quality = judge_essence_quality(user_setting, stats, levels)
            # judge_essence_quality has side effects of logging the result, so
            # the early continue on uncertain recognition should be after it.
            if (
                abandon_label == AbandonStatusLabel.MAYBE_ABANDONED
                or lock_label == LockStatusLabel.MAYBE_LOCKED
            ):
                # early continue on uncertain recognition
                continue
            if lock_label == LockStatusLabel.NOT_LOCKED and (
                (
                    essence_quality == EssenceQuality.TREASURE
                    and user_setting.treasure_action == Action.LOCK
                )
                or (
                    essence_quality == EssenceQuality.TRASH
                    and user_setting.trash_action == Action.LOCK
                )
            ):
                self._window_manager.click(
                    self._profile.LOCK_BUTTON_POS.x, self._profile.LOCK_BUTTON_POS.y
                )
                time.sleep(0.3)
                logger.success("给你自动锁上了，记得保管好哦！(*/ω＼*)")
            elif lock_label == LockStatusLabel.LOCKED and (
                (
                    essence_quality == EssenceQuality.TREASURE
                    and user_setting.treasure_action
                    in [Action.UNLOCK, Action.UNLOCK_AND_UNDEPRECATE]
                )
                or (
                    essence_quality == EssenceQuality.TRASH
                    and user_setting.trash_action
                    in [Action.UNLOCK, Action.UNLOCK_AND_UNDEPRECATE]
                )
            ):
                self._window_manager.click(
                    self._profile.LOCK_BUTTON_POS.x, self._profile.LOCK_BUTTON_POS.y
                )
                time.sleep(0.3)
                logger.success("给你自动解锁了！ヾ(≧▽≦*)o")
            if abandon_label == AbandonStatusLabel.NOT_ABANDONED and (
                (
                    essence_quality == EssenceQuality.TREASURE
                    and user_setting.treasure_action == Action.DEPRECATE
                )
                or (
                    essence_quality == EssenceQuality.TRASH
                    and user_setting.trash_action == Action.DEPRECATE
                )
            ):
                self._window_manager.click(
                    self._profile.DEPRECATE_BUTTON_POS.x,
                    self._profile.DEPRECATE_BUTTON_POS.y,
                )
                time.sleep(0.3)
                logger.success("给你自动标记为弃用了！(￣︶￣)>")
            elif abandon_label == AbandonStatusLabel.ABANDONED and (
                (
                    essence_quality == EssenceQuality.TREASURE
                    and user_setting.treasure_action
                    in [Action.UNDEPRECATE, Action.UNLOCK_AND_UNDEPRECATE]
                )
                or (
                    essence_quality == EssenceQuality.TRASH
                    and user_setting.trash_action
                    in [Action.UNDEPRECATE, Action.UNLOCK_AND_UNDEPRECATE]
                )
            ):
                self._window_manager.click(
                    self._profile.DEPRECATE_BUTTON_POS.x,
                    self._profile.DEPRECATE_BUTTON_POS.y,
                )
                time.sleep(0.3)
                logger.success("给你自动取消弃用啦！(＾Ｕ＾)ノ~ＹＯ")

        else:
            # 扫描完成
            logger.info("基质扫描完成。")

    def stop(self) -> None:
        logger.info("停止基质扫描线程...")
        self._scanning.clear()
