from functools import lru_cache

from .base import (
    LabelT,
    RecognitionProfile,
    TemplateDescriptor,
)
from .brightness_detector import (
    BrightnessDetector,
    BrightnessDetectorProfile,
)
from .recognizer import Recognizer
from .tasks.abandon_lock_status import (
    AbandonStatusLabel,
    LockStatusLabel,
    build_abandon_status_profile,
    build_lock_status_profile,
)
from .tasks.attribute import (
    build_attribute_profile,
)
from .tasks.attribute_level import (
    AttributeLevelRecognizer,
    build_attribute_level_recognizer_profile,
)
from .tasks.ui import (
    UISceneLabel,
    build_ui_scene_profile,
)

# type aliases for recognizers

type AttributeRecognizer = Recognizer[str]
"""识别属性文本的识别器类型别名，返回字符串标签"""

type AbandonStatusRecognizer = Recognizer[AbandonStatusLabel]
"""识别弃用状态的识别器类型别名，返回 AbandonStatusLabel 标签"""

type LockStatusRecognizer = Recognizer[LockStatusLabel]
"""识别上锁状态的识别器类型别名，返回 LockStatusLabel 标签"""

type UISceneRecognizer = Recognizer[UISceneLabel]
"""识别UI场景的识别器类型别名，返回 UISceneLabel 标签"""

# Factory functions


def prepare_recognizer(
    name: str, profile: RecognitionProfile[LabelT]
) -> Recognizer[LabelT]:
    """构造并返回一个识别器实例，并加载其模板。"""
    recognizer = Recognizer(name, profile)
    recognizer.load_templates()
    return recognizer


@lru_cache()
def prepare_attribute_recognizer() -> AttributeRecognizer:
    return prepare_recognizer("AttributeRecognizer", build_attribute_profile())


@lru_cache()
def prepare_abandon_status_recognizer() -> AbandonStatusRecognizer:
    return prepare_recognizer("AbandonStatusRecognizer", build_abandon_status_profile())


@lru_cache()
def prepare_lock_status_recognizer() -> LockStatusRecognizer:
    return prepare_recognizer("LockStatusRecognizer", build_lock_status_profile())


@lru_cache()
def prepare_ui_scene_recognizer() -> UISceneRecognizer:
    return prepare_recognizer("UISceneRecognizer", build_ui_scene_profile())


@lru_cache()
def prepare_attribute_level_recognizer() -> AttributeLevelRecognizer:
    return AttributeLevelRecognizer(
        "AttributeLevelRecognizer", build_attribute_level_recognizer_profile()
    )


__all__ = [
    "LabelT",
    "AbandonStatusLabel",
    "LockStatusLabel",
    "UISceneLabel",
    "AttributeRecognizer",
    "AbandonStatusRecognizer",
    "LockStatusRecognizer",
    "UISceneRecognizer",
    "AttributeLevelRecognizer",
    "TemplateDescriptor",
    "RecognitionProfile",
    "BrightnessDetectorProfile",
    "Recognizer",
    "BrightnessDetector",
    "prepare_recognizer",
    "prepare_attribute_recognizer",
    "prepare_abandon_status_recognizer",
    "prepare_lock_status_recognizer",
    "prepare_ui_scene_recognizer",
    "prepare_attribute_level_recognizer",
]
