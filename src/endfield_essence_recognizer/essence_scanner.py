import threading
import time
from collections.abc import Container

import numpy as np
import pygetwindow

from endfield_essence_recognizer.data import weapons
from endfield_essence_recognizer.log import logger
from endfield_essence_recognizer.recognizer import Recognizer
from endfield_essence_recognizer.window import (
    screenshot_window,
)

# 基质图标位置网格（客户区像素坐标）
# 5 行 9 列，共 45 个图标位置
essence_icon_x_list = np.linspace(128, 1374, 9).astype(int)
essence_icon_y_list = np.linspace(196, 819, 5).astype(int)

# 识别相关常量
RESOLUTION = (1920, 1080)
AREA = (1465, 79, 1883, 532)
DEPRECATE_BUTTON_POS = (1807, 284)
"""弃用按钮点击坐标"""
LOCK_BUTTON_POS = (1839, 286)
"""锁定按钮点击坐标"""
DEPRECATE_BUTTON_ROI = (1790, 270, 1823, 302)
"""弃用按钮截图区域"""
LOCK_BUTTON_ROI = (1825, 270, 1857, 302)
"""锁定按钮截图区域"""
STATS_0_ROI = (1508, 358, 1700, 390)
"""属性 0 截图区域"""
STATS_1_ROI = (1508, 416, 1700, 448)
"""属性 1 截图区域"""
STATS_2_ROI = (1508, 468, 1700, 500)
"""属性 2 截图区域"""


def recognize_once(
    window: pygetwindow.Window,
    text_recognizer: Recognizer,
    icon_recognizer: Recognizer,
) -> None:
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

    logger.opt(colors=True).info(
        f"已识别当前基质，属性: <magenta>{stats}</>, <magenta>{deprecated_text}</>, <magenta>{locked_text}</>"
    )

    if (
        any(stat is None for stat in stats)
        or deprecated_str is None
        or locked_str is None
    ):
        return

    for weapon_id, weapon_data in weapons.items():
        if (
            weapon_data["stats"]["attribute"] == stats[0]
            and weapon_data["stats"]["secondary"] == stats[1]
            and weapon_data["stats"]["skill"] == stats[2]
        ):
            logger.opt(colors=True).success(
                f"这个基质是<green><bold><underline>宝藏</></></>，它完美契合武器<bold>{weapon_data['weaponName']}</>。"
            )
            break
    else:
        logger.opt(colors=True).success(
            "这个基质是<red><bold><underline>垃圾</></></>，它不匹配任何已实装武器。"
        )
