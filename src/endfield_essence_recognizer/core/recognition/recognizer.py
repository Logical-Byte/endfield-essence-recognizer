import importlib.resources
from collections import defaultdict
from typing import Generic

import cv2
from cv2.typing import MatLike

from endfield_essence_recognizer.core.recognition.base import LabelT, RecognitionProfile
from endfield_essence_recognizer.utils.image import load_image
from endfield_essence_recognizer.utils.log import logger, str_properties_and_attrs


class Recognizer(Generic[LabelT]):
    """
    通用图像识别类，使用模板匹配。

    LabelT is the type of the labels used for recognition (e.g., a StrEnum). The return
    value of `recognize_roi` aligns with this type.
    """

    def __init__(self, profile: RecognitionProfile[LabelT]) -> None:
        self.profile = profile
        self._templates: defaultdict[LabelT, list[MatLike]] = defaultdict(list)

        logger.opt(lazy=True).debug(
            "Created Recognizer with profile: {}",
            lambda: str_properties_and_attrs(profile),
        )

    def load_templates(self) -> None:
        """从 profile 中加载所有模板。"""
        logger.debug(f"正在加载 {len(self.profile.templates)} 个模板...")
        for descriptor in self.profile.templates:
            try:
                # 模板通常以灰度图加载
                with importlib.resources.as_file(descriptor.path) as path:
                    image = load_image(path, cv2.IMREAD_GRAYSCALE)
                    if image is None:
                        logger.error(f"无法加载模板图像: {descriptor.path}")
                        continue

                    processed_image = self.profile.preprocess_template(image)
                    self._templates[descriptor.label].append(processed_image)
            except Exception as e:
                logger.error(f"加载模板图像失败 {descriptor.path}: {e}")

    def recognize_roi(self, roi_image: MatLike) -> tuple[LabelT | None, float]:
        """
        识别 ROI 图像中的目标，返回 (标签, 分数)。
        """
        if not self._templates:
            return None, 0.0

        processed_roi = self.profile.preprocess_roi(roi_image)

        # 如果处理后的 ROI 不是灰度图，则转换为灰度图以进行匹配
        if len(processed_roi.shape) == 3:
            processed_roi = cv2.cvtColor(processed_roi, cv2.COLOR_BGR2GRAY)

        best_score = -1.0
        best_label: LabelT | None = None

        for label, templates in self._templates.items():
            for template in templates:
                # 检查模板是否比 ROI 大
                if (
                    template.shape[0] > processed_roi.shape[0]
                    or template.shape[1] > processed_roi.shape[1]
                ):
                    logger.warning(
                        f"标签 '{label}' 的 ROI 图像小于模板: "
                        f"ROI 尺寸={processed_roi.shape[::-1]}, 模板尺寸={template.shape[::-1]}"
                    )
                    continue

                res = cv2.matchTemplate(processed_roi, template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(res)

                if max_val > best_score:
                    best_score = max_val
                    best_label = label

        if best_score >= self.profile.high_threshold:
            return best_label, best_score
        elif best_score >= self.profile.low_threshold:
            logger.warning(f"匹配分数较低: 最佳匹配={best_label} 分数={best_score:.3f}")
            return best_label, best_score
        else:
            logger.warning(f"匹配分数很低: 最佳匹配={best_label} 分数={best_score:.3f}")
            return None, best_score

    def recognize_roi_fallback(
        self, roi_image: MatLike, fallback_label: LabelT
    ) -> tuple[LabelT, float]:
        """
        识别 ROI 图像中的目标，若无匹配则返回 fallback_label。

        返回 (标签, 分数)。
        """
        label, score = self.recognize_roi(roi_image)
        if label is None:
            return fallback_label, score
        return label, score
