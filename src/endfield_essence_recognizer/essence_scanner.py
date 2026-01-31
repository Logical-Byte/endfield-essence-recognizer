import importlib.resources
import threading
import time
from collections.abc import Collection
from typing import Literal

import cv2
import numpy as np
import pyautogui
import pygetwindow

from endfield_essence_recognizer.config import config
from endfield_essence_recognizer.game_data import get_translation, weapon_basic_table
from endfield_essence_recognizer.game_data.item import get_item_name
from endfield_essence_recognizer.game_data.weapon import (
    get_gem_tag_name,
    weapon_stats_dict,
    weapon_type_int_to_translation_key,
)
from endfield_essence_recognizer.image import load_image
from endfield_essence_recognizer.log import logger
from endfield_essence_recognizer.recognizer import Recognizer
from endfield_essence_recognizer.window import (
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
SCROLL_POSITION = (960, 500)
"""鼠标滚轮滚动位置（客户区坐标）"""
SCROLL_TICKS = -100
"""鼠标滚轮滚动量（负数为向下滚动）"""
FIRST_ESSENCE_ROI = ((128, 196), (230, 288))
"""第一个基质截图区域（用于检测滚动是否成功）"""
ESSENCE_SIMILARITY_THRESHOLD = 0.95
"""基质相似度阈值（用于检测重复）"""
MAX_SCROLL_ATTEMPTS = 3
"""最大滚动尝试次数"""
SCROLL_SIMILARITY_THRESHOLD = 0.9
"""滚动成功判定阈值（低于此值认为滚动成功）"""
BOTTOM_DETECTION_ROI = ((128, 196), (1374, 819))
"""底部检测区域（基质网格区域）"""
BOTTOM_SIMILARITY_THRESHOLD = 0.95
"""底部检测相似度阈值"""


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


def scroll_down_window(window: pygetwindow.Window) -> None:
    from endfield_essence_recognizer.window import _get_client_rect

    (left, top), (_right, _bottom) = _get_client_rect(window)
    screen_x = left + SCROLL_POSITION[0]
    screen_y = top + SCROLL_POSITION[1]

    pyautogui.moveTo(screen_x, screen_y)
    pyautogui.scroll(SCROLL_TICKS)


def scroll_to_next_page_robust(window: pygetwindow.Window) -> bool:
    first_essence_before = screenshot_window(window, FIRST_ESSENCE_ROI)

    for attempt in range(MAX_SCROLL_ATTEMPTS):
        scroll_down_window(window)
        time.sleep(0.8)

        first_essence_after = screenshot_window(window, FIRST_ESSENCE_ROI)

        result = cv2.matchTemplate(
            first_essence_before, first_essence_after, cv2.TM_CCOEFF_NORMED
        )
        _, max_val, _, _ = cv2.minMaxLoc(result)

        logger.debug(
            f"滚动尝试 {attempt + 1}/{MAX_SCROLL_ATTEMPTS}，相似度: {max_val:.3f}"
        )

        if max_val < SCROLL_SIMILARITY_THRESHOLD:
            logger.info(f"滚动成功（尝试 {attempt + 1} 次）")
            return True

        logger.debug("第一个基质未变化，继续滚动...")

    logger.warning(f"滚动失败（{MAX_SCROLL_ATTEMPTS} 次尝试后第一个基质仍相同）")
    return False

    first_essence_after = screenshot_window(window, FIRST_ESSENCE_ROI)

    result = cv2.matchTemplate(
        first_essence_before, first_essence_after, cv2.TM_CCOEFF_NORMED
    )
    _, max_val, _, _ = cv2.minMaxLoc(result)

    logger.debug(f"第一个基质相似度: {max_val:.3f}")

    if max_val >= ESSENCE_SIMILARITY_THRESHOLD:
        logger.debug("检测到第一个基质重复，额外滚动一次")
        scroll_down_window(window)
        time.sleep(0.5)


def is_at_bottom_robust(window: pygetwindow.Window) -> bool:
    first_essence = screenshot_window(window, FIRST_ESSENCE_ROI)

    scroll_down_window(window)
    time.sleep(0.8)

    first_essence_after = screenshot_window(window, FIRST_ESSENCE_ROI)

    result = cv2.matchTemplate(first_essence, first_essence_after, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)

    logger.debug(f"底部检测（第一个基质相似度）: {max_val:.3f}")

    return max_val >= BOTTOM_SIMILARITY_THRESHOLD


def judge_essence_quality(stats: list[str | None]) -> Literal["treasure", "trash"]:
    """根据识别到的属性判断基质品质，并输出日志提示。"""

    # 尝试匹配用户自定义的宝藏基质条件
    for treasure_stat in config.treasure_essence_stats:
        if (
            treasure_stat.attribute in stats
            and treasure_stat.secondary in stats
            and treasure_stat.skill in stats
        ):
            logger.opt(colors=True).success(
                "这个基质是<green><bold><underline>宝藏</></></>，因为它符合你设定的宝藏基质条件。"
            )
            return "treasure"

    # 尝试匹配已实装武器
    for weapon_id, weapon_basic in weapon_basic_table.items():
        weapon_stats = weapon_stats_dict[weapon_id]
        if (
            weapon_stats["attribute"] == stats[0]
            and weapon_stats["secondary"] == stats[1]
            and weapon_stats["skill"] == stats[2]
        ):
            # 匹配到已实装武器
            if weapon_id in config.trash_weapon_ids:
                logger.opt(colors=True).warning(
                    f"这个基质虽然匹配武器<bold>{get_item_name(weapon_id, 'CN')}（{weapon_basic_table[weapon_id]['rarity']}★ {get_translation(weapon_type_int_to_translation_key[weapon_id], 'CN')}）</>，但是它被认为是<red><bold><underline>垃圾</></></>。"
                )
                return "trash"
            else:
                logger.opt(colors=True).success(
                    f"这个基质是<green><bold><underline>宝藏</></></>，它完美契合武器<bold>{get_item_name(weapon_id, 'CN')}（{weapon_basic_table[weapon_id]['rarity']}★ {get_translation(weapon_type_int_to_translation_key[weapon_id], 'CN')}）</>。"
                )
                return "treasure"
    else:
        # 未匹配到任何已实装武器
        logger.opt(colors=True).success(
            "这个基质是<red><bold><underline>垃圾</></></>，它不匹配任何已实装武器。"
        )
        return "trash"


def recognize_essence(
    window: pygetwindow.Window, text_recognizer: Recognizer, icon_recognizer: Recognizer
) -> tuple[list[str | None], str | None, str | None]:
    stats: list[str | None] = []

    for k, roi in enumerate([STATS_0_ROI, STATS_1_ROI, STATS_2_ROI]):
        screenshot_image = screenshot_window(window, roi)
        result, max_val = text_recognizer.recognize_roi(screenshot_image)
        stats.append(result)
        logger.debug(f"属性 {k} 识别结果: {result} (分数: {max_val:.3f})")

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

    stats_name = "、".join(
        "无" if stat is None else get_gem_tag_name(stat, "CN") for stat in stats
    )

    logger.opt(colors=True).info(
        f"已识别当前基质，属性: <magenta>{stats_name}</>, <magenta>{deprecated_text}</>, <magenta>{locked_text}</>"
    )

    return stats, deprecated_str, locked_str


def recognize_once(
    window: pygetwindow.Window, text_recognizer: Recognizer, icon_recognizer: Recognizer
) -> None:
    check_scene_result = check_scene(window)
    if not check_scene_result:
        return

    stats, deprecated_str, locked_str = recognize_essence(
        window, text_recognizer, icon_recognizer
    )

    if deprecated_str is None or locked_str is None:
        return

    judge_essence_quality(stats)


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
    ) -> None:
        super().__init__(daemon=True)
        self._scanning = threading.Event()
        self._text_recognizer: Recognizer = text_recognizer
        self._icon_recognizer: Recognizer = icon_recognizer
        self._supported_window_titles: Collection[str] = supported_window_titles

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

        page = 0
        last_essence_stats = None
        while True:
            page += 1
            logger.info(f"开始扫描第 {page} 页...")

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
                stats, deprecated_str, locked_str = recognize_essence(
                    window, self._text_recognizer, self._icon_recognizer
                )

                if deprecated_str is None or locked_str is None:
                    continue

                last_essence_stats = stats

                essence_quality = judge_essence_quality(stats)
                if locked_str == "未锁定" and (
                    (essence_quality == "treasure" and config.treasure_action in "lock")
                    or (essence_quality == "trash" and config.trash_action in "lock")
                ):
                    click_on_window(window, *LOCK_BUTTON_POS)
                    logger.success("给你自动锁上了，记得保管好哦！(*/ω＼*)")
                elif locked_str == "已锁定" and (
                    (
                        essence_quality == "treasure"
                        and config.treasure_action
                        in ["unlock", "unlock_and_undeprecate"]
                    )
                    or (
                        essence_quality == "trash"
                        and config.trash_action in ["unlock", "unlock_and_undeprecate"]
                    )
                ):
                    click_on_window(window, *LOCK_BUTTON_POS)
                    logger.success("给你自动解锁了！ヾ(≧▽≦*)o")
                if deprecated_str == "未弃用" and (
                    (
                        essence_quality == "treasure"
                        and config.treasure_action == "deprecate"
                    )
                    or (
                        essence_quality == "trash"
                        and config.trash_action == "deprecate"
                    )
                ):
                    click_on_window(window, *DEPRECATE_BUTTON_POS)
                    logger.success("给你自动标记为弃用了！(￣︶￣)>")
                elif deprecated_str == "已弃用" and (
                    (
                        essence_quality == "treasure"
                        and config.treasure_action
                        in ["undeprecate", "unlock_and_undeprecate"]
                    )
                    or (
                        essence_quality == "trash"
                        and config.trash_action
                        in ["undeprecate", "unlock_and_undeprecate"]
                    )
                ):
                    click_on_window(window, *DEPRECATE_BUTTON_POS)
                    logger.success("给你自动取消弃用啦！(＾Ｕ＾)ノ~ＹＯ")

            window = get_active_support_window(self._supported_window_titles)
            if window is None:
                logger.info("终末地窗口不在前台，停止基质扫描。")
                self._scanning.clear()
                break

            if not self._scanning.is_set():
                logger.info("基质扫描被中断。")
                break

            scroll_to_next_page_robust(window)

            if is_at_bottom_robust(window):
                logger.info("基质扫描完成。")
                break

    def stop(self) -> None:
        logger.info("停止基质扫描线程...")
        self._scanning.clear()
