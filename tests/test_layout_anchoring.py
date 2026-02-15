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

# ============================================================
# 全局绘制参数
# ============================================================
REF_WIDTH = 1920
REF_HEIGHT = 1080
REF_RATIO = REF_WIDTH / REF_HEIGHT  # 16:9

LINE = 2
DOT = 6
FONT_SIZE = 16

# ============================================================
# 稀有度检测参数（调参区）
# ============================================================
RARITY_COLORS_BGR = {
    1: (155, 155, 155),  # #9B9B9B gray
    2: (66, 206, 171),   # #ABCE42 green
    3: (253, 187, 38),   # #26BBFD blue
    4: (250, 82, 148),   # #9452FA purple
    5: (3, 187, 255),    # #FFBB03 gold
    6: (0, 113, 255),    # #FF7100 orange
}

SAMPLE_STRIP_H = 6        # 采样条高度
SAMPLE_INSET_BOTTOM = -1   # 距卡片底边内缩（正值=向上）
SAMPLE_WIDTH_RATIO = 0.5  # 采样宽度占卡片宽度的比例（居中）
SATURATION_TOP_RATIO = 0.3  # 取饱和度前 N% 的像素

DRAW_CARD_BORDER = True   # 是否绘制卡片边框
DRAW_SAMPLE_AREA = True    # 是否绘制采样区域标记


# ============================================================
# 工具函数
# ============================================================

def _get_font(size: int = FONT_SIZE) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """尝试加载系统中文字体。"""
    candidates = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _put_text(img, text: str, pos: tuple[int, int], color: tuple[int, int, int], font: ImageFont.FreeTypeFont | ImageFont.ImageFont):
    """在 cv2 图像上用 PIL 绘制中文文本。color 为 BGR。"""
    pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)
    rgb = (color[2], color[1], color[0])
    draw.text(pos, text, font=font, fill=rgb)
    result = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    np.copyto(img, result)


def _sample_region(cx: int, cy: int) -> tuple[int, int, int, int]:
    """计算采样区域坐标，返回 (x_left, y_top, x_right, y_bottom)。"""
    half = _CARD_SIZE // 2
    y_bottom = cy + half - SAMPLE_INSET_BOTTOM
    y_top = y_bottom - SAMPLE_STRIP_H
    sample_half_w = int(_CARD_SIZE * SAMPLE_WIDTH_RATIO / 2)
    x_left = cx - sample_half_w
    x_right = cx + sample_half_w
    return x_left, y_top, x_right, y_bottom


# ============================================================
# 缩放
# ============================================================

def scale_image(img):
    """根据宽高比缩放图像，返回 (scaled, new_w, new_h, scale, mode)。"""
    h, w = img.shape[:2]
    ratio = w / h
    if ratio >= REF_RATIO:
        scale = REF_HEIGHT / h
        mode = "宽比例"
    else:
        scale = REF_WIDTH / w
        mode = "窄比例"
    new_w = round(w * scale)
    new_h = round(h * scale)
    scaled = cv2.resize(img, (new_w, new_h))
    return scaled, new_w, new_h, scale, mode


# ============================================================
# 稀有度检测
# ============================================================

def detect_rarity(img, cx: int, cy: int) -> tuple[int, float]:
    """从卡片底部采样高饱和度像素颜色，返回 (稀有度, 距离)。"""
    x_left, y_top, x_right, y_bottom = _sample_region(cx, cy)

    h, w = img.shape[:2]
    y_top = max(0, y_top)
    y_bottom = min(h, y_bottom)
    x_left = max(0, x_left)
    x_right = min(w, x_right)

    strip = img[y_top:y_bottom, x_left:x_right]
    if strip.size == 0:
        return 1, 999.0

    hsv = cv2.cvtColor(strip, cv2.COLOR_BGR2HSV)
    saturations = hsv[:, :, 1].flatten()
    bgr_flat = strip.reshape(-1, 3)

    keep_count = max(1, int(len(saturations) * SATURATION_TOP_RATIO))
    top_indices = np.argpartition(saturations, -keep_count)[-keep_count:]
    top_pixels = bgr_flat[top_indices]

    avg_color = top_pixels.mean(axis=0)

    best_rarity = 1
    best_dist = float("inf")
    for rarity, color in RARITY_COLORS_BGR.items():
        dist = np.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(avg_color, color)))
        if dist < best_dist:
            best_dist = dist
            best_rarity = rarity

    return best_rarity, best_dist


def detect_all_rarities(img, profile: DynamicResolutionProfile) -> list[tuple[int, int, int, float]]:
    """对所有卡片位置检测稀有度，返回 [(cx, cy, rarity, dist), ...]。"""
    results = []
    for cx in profile.essence_icon_x_list:
        for cy in profile.essence_icon_y_list:
            rarity, dist = detect_rarity(img, cx, cy)
            results.append((cx, cy, rarity, dist))
    return results


# ============================================================
# 绘制函数
# ============================================================

def draw_right_panel(scaled, profile, static_data, attr_rec, level_rec, abandon_rec, lock_rec, font):
    """绘制右侧面板：AREA、STATS ROI、按钮、属性识别结果。"""
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

        roi_crop = scaled[roi.y0:roi.y1, roi.x0:roi.x1]
        attr_label, attr_score = attr_rec.recognize_roi(roi_crop)
        level = level_rec.recognize_level(scaled, k, profile)

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

    # 按钮
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

    dep_crop = scaled[dep_roi.y0:dep_roi.y1, dep_roi.x0:dep_roi.x1]
    abandon_label, abandon_score = abandon_rec.recognize_roi_fallback(
        dep_crop, fallback_label=AbandonStatusLabel.MAYBE_ABANDONED
    )
    dep_text = f"{abandon_label.value} ({abandon_score:.2f})"
    _put_text(scaled, dep_text, (dep_roi.x0, dep_roi.y1 + 4), (255, 0, 255), font)
    print(f"  弃用: {dep_text}")

    lock_crop = scaled[lock_roi.y0:lock_roi.y1, lock_roi.x0:lock_roi.x1]
    lock_label, lock_score = lock_rec.recognize_roi_fallback(
        lock_crop, fallback_label=LockStatusLabel.MAYBE_LOCKED
    )
    lock_text = f"{lock_label.value} ({lock_score:.2f})"
    _put_text(scaled, lock_text, (lock_roi.x0, lock_roi.y1 + 4), (0, 0, 255), font)
    print(f"  锁定: {lock_text}")


def draw_grid(scaled, profile, rarity_results, font):
    """绘制左侧物品网格：卡片边框、稀有度标注、采样区域。"""
    for cx, cy, rarity, dist in rarity_results:
        half = _CARD_SIZE // 2

        if DRAW_CARD_BORDER:
            cv2.rectangle(scaled, (cx - half, cy - half), (cx + half, cy + half), (255, 255, 0), LINE)
            cv2.circle(scaled, (cx, cy), DOT, (0, 0, 255), -1)

        rarity_color = RARITY_COLORS_BGR.get(rarity, (255, 255, 255))

        if DRAW_SAMPLE_AREA:
            x_left, y_top, x_right, y_bottom = _sample_region(cx, cy)
            cv2.rectangle(scaled, (x_left, y_top), (x_right, y_bottom), (255, 255, 255), 1)

        _put_text(scaled, f"{rarity}★", (cx - half + 2, cy - half + 2), rarity_color, font)


def draw_bottom_boundary(scaled, new_w, new_h, font):
    """绘制网格底部边界线。"""
    grid_bottom_y = new_h - _BOTTOM_MARGIN
    cv2.line(scaled, (0, grid_bottom_y), (new_w, grid_bottom_y), (0, 200, 200), LINE)
    _put_text(scaled, f"网格底部 y={grid_bottom_y} (margin={_BOTTOM_MARGIN})", (10, grid_bottom_y + 4), (0, 200, 200), font)


def draw_title(scaled, label, new_w, new_h, profile, font):
    """绘制标题。"""
    rows = len(profile.essence_icon_y_list)
    cols = len(profile.essence_icon_x_list)
    title = f"{label} -> {new_w}x{new_h} (DynamicProfile, grid={cols}x{rows})"
    _put_text(scaled, title, (10, 8), (255, 255, 255), font)


# ============================================================
# 初始化与主流程
# ============================================================

def init_recognizers():
    """初始化静态数据和所有识别器。"""
    data_root = importlib.resources.files("endfield_essence_recognizer") / "data/v2"
    static_data = StaticGameData(data_root)
    return (
        static_data,
        prepare_attribute_recognizer(static_data),
        prepare_attribute_level_recognizer(),
        prepare_abandon_status_recognizer(),
        prepare_lock_status_recognizer(),
    )


def annotate_screenshot(img_path, output_dir, static_data, attr_rec, level_rec, abandon_rec, lock_rec, font):
    img = cv2.imread(str(img_path))
    if img is None:
        print(f"无法读取: {img_path}")
        return

    h, w = img.shape[:2]
    label = f"{w}x{h}"

    scaled, new_w, new_h, scale, mode = scale_image(img)
    print(f"{label} -> 缩放后: {new_w}x{new_h} (scale={scale:.4f}, {mode})")

    profile = DynamicResolutionProfile(new_w, new_h)

    # 稀有度检测（在任何绘制之前）
    rarity_results = detect_all_rarities(scaled, profile)

    # 绘制各部分
    draw_right_panel(scaled, profile, static_data, attr_rec, level_rec, abandon_rec, lock_rec, font)
    draw_grid(scaled, profile, rarity_results, font)
    draw_bottom_boundary(scaled, new_w, new_h, font)
    draw_title(scaled, label, new_w, new_h, profile, font)

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
