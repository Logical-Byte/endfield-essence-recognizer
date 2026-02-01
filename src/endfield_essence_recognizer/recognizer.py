import importlib.resources
import itertools
from collections import defaultdict
from collections.abc import Callable
from importlib.abc import Traversable

import cv2
from cv2.typing import MatLike

from endfield_essence_recognizer.game_data import gem_table
from endfield_essence_recognizer.game_data.weapon import get_gem_tag_name
from endfield_essence_recognizer.utils.image import (
    linear_operation,
    load_image,
    to_gray_image,
)
from endfield_essence_recognizer.utils.log import logger

# 识别阈值（默认值，可在 Recognizer 中覆盖）
HIGH_THRESH = 0.75  # 高分数阈值：超过此值直接判定
LOW_THRESH = 0.50  # 低分数阈值：低于此值判定为未知


def preprocess_text_roi(roi_image: MatLike) -> MatLike:
    """对 ROI 图像进行预处理，提升识别效果。"""
    gray = to_gray_image(roi_image)
    enhanced = linear_operation(gray, 100, 255)
    return enhanced


def preprocess_text_template(template_image: MatLike) -> MatLike:
    """对模板图像进行预处理，提升识别效果。"""
    return linear_operation(template_image, 128, 255)


def get_label_name(label: str) -> str:
    """获取标签的显示名称。"""
    if label in gem_table:
        return get_gem_tag_name(label, "CN")
    return label


class Recognizer:
    def __init__(
        self,
        labels: list[str],
        templates_dir: Traversable,
        high_thresh: float = HIGH_THRESH,
        low_thresh: float = LOW_THRESH,
        preprocess_roi: Callable[[MatLike], MatLike] | None = None,
        preprocess_template: Callable[[MatLike], MatLike] | None = None,
    ) -> None:
        self.labels: list[str] = labels
        self.templates_dir: Traversable = templates_dir
        self.high_thresh: float = high_thresh
        self.low_thresh: float = low_thresh
        self.preprocess_roi: Callable[[MatLike], MatLike] = (
            preprocess_roi if preprocess_roi is not None else lambda x: x
        )
        self.preprocess_template: Callable[[MatLike], MatLike] = (
            preprocess_template if preprocess_template is not None else lambda x: x
        )
        self._templates: defaultdict[str, list[MatLike]] = defaultdict(list)
        self._suffixes: list[str] = [
            ".png",
            ".jpg",
            ".jpeg",
            ".bmp",
            ".tiff",
            ".webp",
            ".gif",
            ".tif",
        ]

    def load_templates(self) -> None:
        logger.info(f"正在从目录加载模板: {self.templates_dir}...")
        if not self.templates_dir.is_dir():
            logger.error(f"模板目录未找到: {self.templates_dir}")
            return

        for label in self.labels:
            with importlib.resources.as_file(self.templates_dir) as templates_dir_path:
                for path in itertools.chain(
                    templates_dir_path.glob(label + "*"),
                    (templates_dir_path / label).glob("**/*"),
                ):
                    if path.suffix.lower() in self._suffixes and path.is_file():
                        try:
                            image = load_image(path, cv2.IMREAD_GRAYSCALE)
                            image = self.preprocess_template(image)
                            self._templates[label].append(image)
                        except Exception as e:
                            logger.error(f"加载模板图像失败 {path}: {e}")
            if not self._templates[label]:
                logger.error(f'在 {self.templates_dir} 中未找到标签 "{label}" 的模板')

    def recognize_roi(self, roi_image: MatLike) -> tuple[str | None, float]:
        """
        识别 ROI 图像中的短语，返回 (标签, 分数)。

        Args:
            roi_img: ROI 区域的图像（OpenCV 格式）

        Returns:
            (标签, 分数) 元组。如果无法识别，返回 (None, best_score)。
        """

        if not self._templates:
            self.load_templates()

        image_height, image_width = roi_image.shape[:2]
        gray = to_gray_image(roi_image)

        best_label = None
        best_label_name = "无匹配"
        best_score = -float("inf")
        for label, templates in self._templates.items():
            label_name = get_label_name(label)
            for template in templates:
                template_height, template_width = template.shape[:2]
                if image_height < template_height or image_width < template_width:
                    logger.warning(
                        f"标签 '{label_name}' 的 ROI 图像小于模板: "
                        f"ROI 尺寸={gray.shape[::-1]}, 模板尺寸={template.shape[::-1]}"
                    )
                    continue
                result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
                _minVal, maxVal, _minLoc, _maxLoc = cv2.minMaxLoc(result)
                logger.trace(f"模板匹配: 最佳匹配={label_name} 分数={maxVal:.3f}")
                if maxVal > best_score:
                    best_score = maxVal
                    best_label = label
                    best_label_name = label_name

        if best_score >= self.high_thresh:
            return best_label, float(best_score)
        elif best_score >= self.low_thresh:
            logger.warning(
                f"匹配分数较低: 最佳匹配={best_label_name} 分数={best_score:.3f}"
            )
            return best_label, float(best_score)
        else:
            logger.warning(
                f"匹配分数很低: 最佳匹配={best_label_name} 分数={best_score:.3f}"
            )
            return None, float(best_score)
