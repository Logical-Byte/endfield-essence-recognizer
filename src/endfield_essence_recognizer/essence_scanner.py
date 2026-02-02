import importlib.resources
import threading
import time
from collections.abc import Collection
from typing import Literal

import cv2
import numpy as np
import pygetwindow
from cv2.typing import MatLike

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
from endfield_essence_recognizer.recognizer import Recognizer
from endfield_essence_recognizer.services.user_setting_manager import UserSettingManager
from endfield_essence_recognizer.utils.image import load_image, to_gray_image
from endfield_essence_recognizer.utils.log import logger
from endfield_essence_recognizer.utils.window import (
    click_on_window,
    get_active_support_window,
    get_client_size,
    get_support_window,
    screenshot_window,
)

# 基质图标位置网格（客户区像素坐标）
# 5 行 9 列，共 45 个图标位置
essence_icon_x_list = np.linspace(128, 1374, 9).astype(int)
essence_icon_y_list = np.linspace(196, 819, 5).astype(int)

# 识别相关常量
RESOLUTION = (1920, 1080)
ESSENCE_UI_ROI = ((38, 66), (143, 106))
ESSENCE_UI_TEMPLATE_PATH = (
    importlib.resources.files("endfield_essence_recognizer")
    / "templates/screenshot/武器基质.png"
)
AREA = ((1465, 79), (1883, 532))
DEPRECATE_BUTTON_POS = (1807, 284)
"""弃用按钮点击坐标"""
LOCK_BUTTON_POS = (1839, 286)
"""锁定按钮点击坐标"""
DEPRECATE_BUTTON_ROI = ((1790, 270), (1823, 302))
"""弃用按钮截图区域"""
LOCK_BUTTON_ROI = ((1825, 270), (1857, 302))
"""锁定按钮截图区域"""
STATS_0_ROI = ((1508, 358), (1700, 390))
"""属性 0 截图区域"""
STATS_1_ROI = ((1508, 416), (1700, 448))
"""属性 1 截图区域"""
STATS_2_ROI = ((1508, 468), (1700, 500))
"""属性 2 截图区域"""

STATS_0_LEVEL_ICONS = [
    (1503, 395),  # +1
    (1520, 395),  # +2
    (1538, 395),  # +3
    (1554, 395),  # +4
]
"""属性 0 等级图标坐标"""
STATS_1_LEVEL_ICONS = [
    (1503, 452),  # +1
    (1520, 452),  # +2
    (1538, 452),  # +3
    (1554, 452),  # +4
]
"""属性 1 等级图标坐标"""
STATS_2_LEVEL_ICONS = [
    (1503, 507),  # +1
    (1520, 507),  # +2
    (1538, 507),  # +3
    (1554, 507),  # +4
]
"""属性 2 等级图标坐标"""
LEVEL_ICON_SAMPLE_RADIUS = 2
"""等级图标状态采样半径"""


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
    image: MatLike, icon_points: list[tuple[int, int]]
) -> int | None:
    """
    根据坐标点列表识别等级。

    Args:
        image: 全局图像（客户区截图）
        icon_points: 4个图标的坐标点列表 [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]

    Returns:
        等级 (1-4) 或 None（识别失败）
    """
    gray = to_gray_image(image)

    # 检测每个图标的状态
    active_count = 0
    for i, (x, y) in enumerate(icon_points):
        is_active = detect_icon_state_at_point(gray, x, y, LEVEL_ICON_SAMPLE_RADIUS)
        logger.trace(f"图标 {i + 1} ({x},{y}) 状态: {'白色' if is_active else '灰色'}")
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


def check_scene(window: pygetwindow.Window) -> bool:
    width, height = get_client_size(window)
    if (width, height) != RESOLUTION:
        logger.warning(
            f"检测到终末地窗口的客户区尺寸为 {width}x{height}，请将终末地分辨率调整为 {RESOLUTION[0]}x{RESOLUTION[1]} 窗口。"
        )
        return False

    screenshot = screenshot_window(window, ESSENCE_UI_ROI)
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


def judge_essence_quality(
    setting: UserSetting,
    stats: list[str | None],
    levels: list[int | None] | None = None,
) -> Literal["treasure", "trash"]:
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
            return "treasure"

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
            return "treasure"
        else:
            logger.opt(colors=True).success(
                "这个基质是<red><bold><underline>养成材料</></></>，它不匹配任何已实装武器。"
            )
            return "trash"
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
        return "treasure"
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
            return "treasure"
        else:
            logger.opt(colors=True).warning(
                f"这个基质虽然匹配武器{weapons_description_str}，但匹配的所有武器均已被用户手动拦截，"
                f"因此这个基质是<red><bold><underline>养成材料</></></>。"
            )
            return "trash"


def recognize_essence(
    window: pygetwindow.Window, text_recognizer: Recognizer, icon_recognizer: Recognizer
) -> tuple[list[str | None], list[int | None], str | None, str | None]:
    stats: list[str | None] = []
    levels: list[int | None] = []

    # 截取客户区全局截图用于等级检测
    full_screenshot = screenshot_window(window)

    for k, roi in enumerate([STATS_0_ROI, STATS_1_ROI, STATS_2_ROI]):
        screenshot_image = screenshot_window(window, roi)
        result, max_val = text_recognizer.recognize_roi(screenshot_image)
        stats.append(result)
        logger.debug(f"属性 {k} 识别结果: {result} (分数: {max_val:.3f})")

        # 识别等级（通过检测坐标点状态）
        icon_points = [STATS_0_LEVEL_ICONS, STATS_1_LEVEL_ICONS, STATS_2_LEVEL_ICONS][k]
        level_value = recognize_level_from_icon_points(full_screenshot, icon_points)
        levels.append(level_value)

        if level_value is not None:
            logger.debug(f"属性 {k} 等级识别结果: +{level_value}")
        else:
            logger.debug(f"属性 {k} 等级识别结果: 无法识别")

    screenshot_image = screenshot_window(window, DEPRECATE_BUTTON_ROI)
    deprecated_str, max_val = icon_recognizer.recognize_roi(screenshot_image)
    deprecated_text = (
        deprecated_str if deprecated_str is not None else "不知道是否已弃用"
    )
    logger.debug(f"弃用按钮识别结果: {deprecated_str} (分数: {max_val:.3f})")

    screenshot_image = screenshot_window(window, LOCK_BUTTON_ROI)
    locked_str, max_val = icon_recognizer.recognize_roi(screenshot_image)
    locked_text = locked_str if locked_str is not None else "不知道是否已锁定"
    logger.debug(f"锁定按钮识别结果: {locked_str} (分数: {max_val:.3f})")

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
        f"已识别当前基质，属性: <magenta>{stats_name}</>, <magenta>{deprecated_text}</>, <magenta>{locked_text}</>"
    )

    return stats, levels, deprecated_str, locked_str


def recognize_once(
    window: pygetwindow.Window,
    text_recognizer: Recognizer,
    icon_recognizer: Recognizer,
    user_setting: UserSetting,
) -> None:
    check_scene_result = check_scene(window)
    if not check_scene_result:
        return

    stats, levels, deprecated_str, locked_str = recognize_essence(
        window, text_recognizer, icon_recognizer
    )

    if deprecated_str is None or locked_str is None:
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
        text_recognizer: Recognizer,
        icon_recognizer: Recognizer,
        supported_window_titles: Collection[str],
        user_setting_manager: UserSettingManager,
    ) -> None:
        super().__init__(daemon=True)
        self._scanning = threading.Event()
        self._text_recognizer: Recognizer = text_recognizer
        self._icon_recognizer: Recognizer = icon_recognizer
        self._supported_window_titles: Collection[str] = supported_window_titles
        self._user_setting_manager: UserSettingManager = user_setting_manager

    def run(self) -> None:
        logger.info("开始基质扫描线程...")
        self._scanning.set()

        window = get_support_window(self._supported_window_titles)
        if window is None:
            logger.info("未找到终末地窗口，停止基质扫描。")
            self._scanning.clear()
            return
        if window.isMinimized:
            window.restore()
            time.sleep(0.5)
        if not window.isActive:
            window.activate()
            time.sleep(0.5)

        check_scene_result = check_scene(window)
        if not check_scene_result:
            self._scanning.clear()
            return

        # 获取当前用户设置的快照，用于接下来的判断
        user_setting = self._user_setting_manager.get_user_setting()

        for i, j in np.ndindex(len(essence_icon_y_list), len(essence_icon_x_list)):
            window = get_active_support_window(self._supported_window_titles)
            if window is None:
                logger.info("终末地窗口不在前台，停止基质扫描。")
                self._scanning.clear()
                break

            if not self._scanning.is_set():
                logger.info("基质扫描被中断。")
                break

            logger.info(f"正在扫描第 {i + 1} 行第 {j + 1} 列的基质...")

            # 点击基质图标位置
            relative_x = essence_icon_x_list[j]
            relative_y = essence_icon_y_list[i]
            click_on_window(window, relative_x, relative_y)

            # 等待短暂时间以确保界面更新
            time.sleep(0.3)

            # 识别基质信息
            stats, levels, deprecated_str, locked_str = recognize_essence(
                window, self._text_recognizer, self._icon_recognizer
            )

            if deprecated_str is None or locked_str is None:
                continue

            essence_quality = judge_essence_quality(user_setting, stats, levels)
            if locked_str == "未锁定" and (
                (
                    essence_quality == "treasure"
                    and user_setting.treasure_action == Action.LOCK
                )
                or (
                    essence_quality == "trash"
                    and user_setting.trash_action == Action.LOCK
                )
            ):
                click_on_window(window, *LOCK_BUTTON_POS)
                time.sleep(0.3)
                logger.success("给你自动锁上了，记得保管好哦！(*/ω＼*)")
            elif locked_str == "已锁定" and (
                (
                    essence_quality == "treasure"
                    and user_setting.treasure_action
                    in [Action.UNLOCK, Action.UNLOCK_AND_UNDEPRECATE]
                )
                or (
                    essence_quality == "trash"
                    and user_setting.trash_action
                    in [Action.UNLOCK, Action.UNLOCK_AND_UNDEPRECATE]
                )
            ):
                click_on_window(window, *LOCK_BUTTON_POS)
                time.sleep(0.3)
                logger.success("给你自动解锁了！ヾ(≧▽≦*)o")
            if deprecated_str == "未弃用" and (
                (
                    essence_quality == "treasure"
                    and user_setting.treasure_action == Action.DEPRECATE
                )
                or (
                    essence_quality == "trash"
                    and user_setting.trash_action == Action.DEPRECATE
                )
            ):
                click_on_window(window, *DEPRECATE_BUTTON_POS)
                time.sleep(0.3)
                logger.success("给你自动标记为弃用了！(￣︶￣)>")
            elif deprecated_str == "已弃用" and (
                (
                    essence_quality == "treasure"
                    and user_setting.treasure_action
                    in [Action.UNDEPRECATE, Action.UNLOCK_AND_UNDEPRECATE]
                )
                or (
                    essence_quality == "trash"
                    and user_setting.trash_action
                    in [Action.UNDEPRECATE, Action.UNLOCK_AND_UNDEPRECATE]
                )
            ):
                click_on_window(window, *DEPRECATE_BUTTON_POS)
                time.sleep(0.3)
                logger.success("给你自动取消弃用啦！(＾Ｕ＾)ノ~ＹＯ")

        else:
            # 扫描完成
            logger.info("基质扫描完成。")

    def stop(self) -> None:
        logger.info("停止基质扫描线程...")
        self._scanning.clear()
