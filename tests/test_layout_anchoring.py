"""
布局定位与属性识别验证测试

读取 tests/screenshot/ 下的截图，根据宽高比选择缩放策略：
- 宽比例 (>= 16:9)：按高度缩放到 1080
- 窄比例 (< 16:9)：按宽度缩放到 1920

使用 DynamicResolutionProfile 绘制所有 ROI 和按钮位置，
并对 STATS ROI 执行属性识别，将结果标注在图像上，
输出到 tests/screenshot/analysis/ 目录。

运行: python tests/test_layout_anchoring.py
"""

import importlib.resources
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from endfield_essence_recognizer.core.layout.dynamic import (
    DynamicResolutionProfile,
    _BOTTOM_MARGIN,
    _CARD_SIZE,
)
from endfield_essence_recognizer.core.recognition import (
    prepare_attribute_recognizer,
    prepare_attribute_level_recognizer,
    prepare_abandon_status_recognizer,
    prepare_lock_status_recognizer,
)
from endfield_essence_recognizer.core.recognition.tasks.abandon_lock_status import (
    AbandonStatusLabel,
    LockStatusLabel,
)
from endfield_essence_recognizer.game_data.static_game_data import StaticGameData

REF_WIDTH = 1920
REF_HEIGHT = 1080
REF_RATIO = REF_WIDTH / REF_HEIGHT  # 16:9

LINE = 3
DOT = 8
FONT_SIZE = 18


def _get_font(size: int = FONT_SIZE) -> ImageFont.FreeTypeFont:
    """尝试加载系统中文字体。"""
    candidates = [
        "C:/Windows/Fonts/msyh.ttc",    # 微软雅黑
        "C:/Windows/Fonts/simhei.ttf",   # 黑体
        "C:/Windows/Fonts/simsun.ttc",   # 宋体
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _put_text(img, text: str, pos: tuple[int, int], color: tuple[int, int, int], font: ImageFont.FreeTypeFont):
    """在 cv2 图像上用 PIL 绘制中文文本。color 为 BGR。"""
    pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)
    # PIL 用 RGB，cv2 用 BGR
    rgb = (color[2], color[1], color[0])
    draw.text(pos, text, font=font, fill=rgb)
    result = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    np.copyto(img, result)


def init_recognizers():
    """初始化静态数据和所有识别器。"""
    data_root = importlib.resources.files("endfield_essence_recognizer") / "data/v2"
    static_data = StaticGameData(data_root)

    attr_recognizer = prepare_attribute_recognizer(static_data)
    level_recognizer = prepare_attribute_level_recognizer()
    abandon_recognizer = prepare_abandon_status_recognizer()
    lock_recognizer = prepare_lock_status_recognizer()

    return static_data, attr_recognizer, level_recognizer, abandon_recognizer, lock_recognizer


def annotate_screenshot(img_path, output_dir, static_data, attr_rec, level_rec, abandon_rec, lock_rec, font):
    img = cv2.imread(str(img_path))
    if img is None:
        print(f"无法读取: {img_path}")
        return

    h, w = img.shape[:2]
    label = f"{w}x{h}"
    ratio = w / h

    if ratio >= REF_RATIO:
        scale = REF_HEIGHT / h
    else:
        scale = REF_WIDTH / w

    new_w = round(w * scale)
    new_h = round(h * scale)
    scaled = cv2.resize(img, (new_w, new_h))

    mode = "宽比例" if ratio >= REF_RATIO else "窄比例"
    print(f"{label} -> 缩放后: {new_w}x{new_h} (scale={scale:.4f}, {mode})")

    profile = DynamicResolutionProfile(new_w, new_h)

    # --- 绘制布局 ---

    # AREA
    area = profile.AREA
    cv2.rectangle(scaled, (area.x0, area.y0), (area.x1, area.y1), (0, 255, 0), LINE)
    _put_text(scaled, "AREA", (area.x0, area.y0 - FONT_SIZE - 4), (0, 255, 0), font)

    # STATS ROIs + 属性识别
    rois = [
        ("STATS_0", profile.STATS_0_ROI, (255, 0, 0)),
        ("STATS_1", profile.STATS_1_ROI, (255, 100, 0)),
        ("STATS_2", profile.STATS_2_ROI, (255, 200, 0)),
    ]
    for k, (name, roi, color) in enumerate(rois):
        cv2.rectangle(scaled, (roi.x0, roi.y0), (roi.x1, roi.y1), color, LINE)

        # 属性识别
        roi_crop = scaled[roi.y0:roi.y1, roi.x0:roi.x1]
        attr_label, attr_score = attr_rec.recognize_roi(roi_crop)

        # 等级识别
        level = level_rec.recognize_level(scaled, k, profile)

        # 构建显示文本
        if attr_label:
            stat = static_data.get_stat(attr_label)
            attr_name = stat.name if stat else attr_label
            text = f"{name}: {attr_name} ({attr_score:.2f})"
            if level is not None:
                text += f" +{level}"
        else:
            text = f"{name}: ? ({attr_score:.2f})"

        _put_text(scaled, text, (roi.x0, roi.y0 - FONT_SIZE - 4), color, font)
        print(f"  {text}")

    # 按钮位置
    lock = profile.LOCK_BUTTON_POS
    dep = profile.DEPRECATE_BUTTON_POS
    cv2.circle(scaled, (lock.x, lock.y), DOT, (0, 0, 255), -1)
    _put_text(scaled, "LOCK", (lock.x + 12, lock.y - FONT_SIZE // 2), (0, 0, 255), font)
    cv2.circle(scaled, (dep.x, dep.y), DOT, (255, 0, 255), -1)
    _put_text(scaled, "DEP", (dep.x + 12, dep.y - FONT_SIZE // 2), (255, 0, 255), font)

    # 按钮 ROI + 状态识别
    lock_roi = profile.LOCK_BUTTON_ROI
    dep_roi = profile.DEPRECATE_BUTTON_ROI
    cv2.rectangle(scaled, (lock_roi.x0, lock_roi.y0), (lock_roi.x1, lock_roi.y1), (0, 0, 255), LINE)
    cv2.rectangle(scaled, (dep_roi.x0, dep_roi.y0), (dep_roi.x1, dep_roi.y1), (255, 0, 255), LINE)

    # 弃用状态识别
    dep_crop = scaled[dep_roi.y0:dep_roi.y1, dep_roi.x0:dep_roi.x1]
    abandon_label, abandon_score = abandon_rec.recognize_roi_fallback(
        dep_crop, fallback_label=AbandonStatusLabel.MAYBE_ABANDONED
    )
    dep_text = f"{abandon_label.value} ({abandon_score:.2f})"
    _put_text(scaled, dep_text, (dep_roi.x0, dep_roi.y1 + 4), (255, 0, 255), font)
    print(f"  弃用: {dep_text}")

    # 锁定状态识别
    lock_crop = scaled[lock_roi.y0:lock_roi.y1, lock_roi.x0:lock_roi.x1]
    lock_label, lock_score = lock_rec.recognize_roi_fallback(
        lock_crop, fallback_label=LockStatusLabel.MAYBE_LOCKED
    )
    lock_text = f"{lock_label.value} ({lock_score:.2f})"
    _put_text(scaled, lock_text, (lock_roi.x0, lock_roi.y1 + 4), (0, 0, 255), font)
    print(f"  锁定: {lock_text}")

    # 物品网格图标
    for cx in profile.essence_icon_x_list:
        for cy in profile.essence_icon_y_list:
            half = _CARD_SIZE // 2
            cv2.rectangle(scaled, (cx - half, cy - half), (cx + half, cy + half), (255, 255, 0), LINE)
            cv2.circle(scaled, (cx, cy), DOT, (0, 0, 255), -1)

    # 网格底部边界线
    grid_bottom_y = new_h - _BOTTOM_MARGIN
    cv2.line(scaled, (0, grid_bottom_y), (new_w, grid_bottom_y), (0, 200, 200), LINE)
    _put_text(scaled, f"网格底部 y={grid_bottom_y} (margin={_BOTTOM_MARGIN})", (10, grid_bottom_y + 4), (0, 200, 200), font)

    # 标题
    rows = len(profile.essence_icon_y_list)
    cols = len(profile.essence_icon_x_list)
    title = f"{label} -> {new_w}x{new_h} (DynamicProfile, grid={cols}x{rows})"
    _put_text(scaled, title, (10, 8), (255, 255, 255), font)

    out = output_dir / f"anchored_{label}.png"
    cv2.imwrite(str(out), scaled)
    print(f"  -> 保存: {out}")


def main():
    print("=" * 60)
    print("布局定位与属性识别验证测试")
    print("=" * 60)

    screenshots_dir = Path("tests/screenshot")
    output_dir = screenshots_dir / "analysis"
    output_dir.mkdir(exist_ok=True)

    screenshot_files = sorted(screenshots_dir.glob("*.png"))
    if not screenshot_files:
        print(f"\n在 {screenshots_dir} 中没有找到截图")
        return

    print(f"\n找到 {len(screenshot_files)} 个截图")
    print("正在加载识别器...")
    static_data, attr_rec, level_rec, abandon_rec, lock_rec = init_recognizers()
    font = _get_font()
    print("识别器加载完成\n")

    for img_path in screenshot_files:
        annotate_screenshot(img_path, output_dir, static_data, attr_rec, level_rec, abandon_rec, lock_rec, font)

    print(f"\n所有标注图像已保存到: {output_dir}")


if __name__ == "__main__":
    main()
