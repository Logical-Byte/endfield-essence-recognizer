"""
截图隐私处理工具

遮蔽 tests/screenshot/ 下所有截图左下角的 UID 信息，防止隐私泄漏。
处理后的图像直接覆盖原文件。

运行: python scripts/mask_screenshot_uid.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import cv2

from endfield_essence_recognizer.core.layout.res_1080p import Resolution1080p

_BASE = Resolution1080p()
# UID 遮罩区域（1080p 基准）
_UID_REGION = _BASE.MASK_ESSENCE_REGION_UID


def mask_uid(img_path: Path) -> None:
    img = cv2.imread(str(img_path))
    if img is None:
        print(f"无法读取: {img_path}")
        return

    h, w = img.shape[:2]

    # 按原始分辨率等比映射 UID 区域
    scale_x = w / 1920
    scale_y = h / 1080
    x0 = round(_UID_REGION.x0 * scale_x)
    y0 = round(_UID_REGION.y0 * scale_y)
    x1 = round(_UID_REGION.x1 * scale_x)
    y1 = round(_UID_REGION.y1 * scale_y)

    cv2.rectangle(img, (x0, y0), (x1, y1), (0, 0, 0), -1)
    cv2.imwrite(str(img_path), img)
    print(f"已遮蔽: {img_path} ({w}x{h}) 区域=({x0},{y0})-({x1},{y1})")


def main():
    screenshots_dir = Path("tests/screenshot")
    files = sorted(screenshots_dir.glob("*.png"))

    if not files:
        print("没有找到截图")
        return

    print(f"找到 {len(files)} 个截图\n")
    for f in files:
        mask_uid(f)

    print("\n处理完成")


if __name__ == "__main__":
    main()
