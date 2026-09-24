"""
截图隐私处理工具

遮蔽输入目录下所有截图左下角的 UID 信息，防止隐私泄漏。
处理后的图像直接覆盖原文件。

运行示例:
python scripts/mask_screenshot_uid.py
python scripts/mask_screenshot_uid.py tests/screenshot
python scripts/mask_screenshot_uid.py tests/screenshot -g "*.png"
"""

import argparse
from pathlib import Path

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量遮蔽截图中的 UID 区域")
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path("tests/screenshot"),
        help="输入截图目录",
    )
    parser.add_argument(
        "-g",
        "--glob",
        default="*.png",
        help="输入文件匹配模式（默认: *.png）",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    screenshots_dir = args.input
    files = sorted(screenshots_dir.glob(args.glob))

    if not files:
        print(f"在 {screenshots_dir} 中没有找到匹配 {args.glob} 的截图")
        return

    print(f"找到 {len(files)} 个截图\n")
    for f in files:
        mask_uid(f)

    print("\n处理完成")


if __name__ == "__main__":
    main()
