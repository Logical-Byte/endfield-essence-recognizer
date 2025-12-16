import logging
from collections.abc import Sequence
from pathlib import Path

import cv2
import numpy as np
from cv2.typing import MatLike

# 识别ROI区域（客户区像素坐标）
# 该区域显示基质的属性文本，如"智识提升"等
BONUS_ROI = (1508, 359, 1680, 390)  # (x1, y1, x2, y2)

# 识别标签列表（所有可能的属性文本）
BONUS_LABELS = ["智识提升", "敏捷提升", "力量提升", "意志提升", "全能力提升"]
BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"  # 模板图片目录

# 识别阈值（默认值，可在 Recognizer 中覆盖）
HIGH_THRESH = 0.90  # 高置信度阈值：超过此值直接判定
LOW_THRESH = 0.80  # 低置信度阈值：低于此值判定为未知

# ============================================================================
# 图像处理函数
# ============================================================================


def load_image(
    image_like: str | Path | bytes | MatLike, flags: cv2.ImreadModes = cv2.IMREAD_COLOR
) -> MatLike:
    if isinstance(image_like, str | Path):
        return cv2.imdecode(np.fromfile(image_like, dtype=np.uint8), flags)
    elif isinstance(image_like, bytes | bytearray | memoryview):
        return cv2.imdecode(np.frombuffer(image_like, dtype=np.uint8), flags)
    else:
        return image_like


def save_image(
    image: MatLike,
    path: str | Path,
    ext: str = ".png",
    params: Sequence[int] | None = None,
) -> bool:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    success, buffer = cv2.imencode(ext, image, params or [])
    path.write_bytes(buffer)
    return success


# ============================================================================
# 模板匹配与识别
# ============================================================================


class Recognizer:
    """封装模板加载与ROI识别逻辑，便于复用与测试。"""

    def __init__(
        self,
        roi: tuple[int, int, int, int] = BONUS_ROI,
        labels: list[str] | None = None,
        templates_dir: Path = TEMPLATES_DIR,
        high_thresh: float = HIGH_THRESH,
        low_thresh: float = LOW_THRESH,
    ) -> None:
        self.roi = roi
        self.labels = labels or BONUS_LABELS
        self.templates_dir = templates_dir
        self.high_thresh = high_thresh
        self.low_thresh = low_thresh
        self._template_cache: dict[str, list[np.ndarray]] = {}
        self._exts = (".png", ".bmp", ".jpg", ".jpeg")

    def load_templates_once(self) -> None:
        """懒加载模板到内存缓存。"""
        if self._template_cache:
            return
        if not self.templates_dir.exists():
            logging.warning(f"Templates dir not found: {self.templates_dir}")
            return
        loaded = 0
        for label in self.labels:
            bucket: list[np.ndarray] = []
            for p in list(self.templates_dir.glob(label + "*")) + list(
                (self.templates_dir / label).glob("**/*")
            ):
                if p.is_file() and p.suffix.lower() in self._exts:
                    im = load_image(p, cv2.IMREAD_GRAYSCALE)
                    if im is not None:
                        bucket.append(im)
                        loaded += 1
            if bucket:
                self._template_cache[label] = bucket
        logging.info(
            f"Templates loaded: {loaded} images in {len(self._template_cache)} labels"
        )

    def recognize(self, roi_img: MatLike) -> tuple[str | None, float | None]:
        """
        识别 ROI 图像中的短语，返回(标签, 置信度)。

        Args:
            roi_img: ROI 区域的图像（BGR 格式，OpenCV 格式）

        Returns:
            (标签, 置信度) 元组。如果无法识别，返回 (None, best_score) 或 (None, None)
        """
        self.load_templates_once()
        if roi_img is None:
            logging.warning("ROI image is None")
            return None, None
        if not self._template_cache:
            logging.warning("No templates loaded; please add images under templates/")
            return None, None

        gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY)

        best_label = None
        best_score = -float("inf")
        for label, tmps in self._template_cache.items():
            for tmpl in tmps:
                th, tw = tmpl.shape[:2]
                if gray.shape[0] < th or gray.shape[1] < tw:
                    continue
                res = cv2.matchTemplate(gray, tmpl, cv2.TM_CCOEFF_NORMED)
                _minVal, maxVal, _minLoc, _maxLoc = cv2.minMaxLoc(res)
                logging.debug(f"Template match: label={label} maxVal={maxVal:.3f}")
                if maxVal > best_score:
                    best_score = maxVal
                    best_label = label

        if best_label is None:
            return None, None

        if best_score >= self.high_thresh:
            return best_label, float(best_score)
        if best_score >= self.low_thresh:
            logging.info(
                f"Match in gray zone: label={best_label} score={best_score:.3f}"
            )
            return best_label, float(best_score)

        logging.info(
            f"Best match below low threshold: label={best_label} score={best_score:.3f}"
        )
        return None, float(best_score)
