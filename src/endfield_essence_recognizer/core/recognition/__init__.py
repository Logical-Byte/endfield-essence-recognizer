from functools import lru_cache

from .base import (
    LabelT,
    RecognitionProfile,
    TemplateDescriptor,
)
from .recognizer import Recognizer
from .tasks import (
    StatusLabel,
    build_attribute_profile,
    build_status_profile,
)

StatusRecognizer = Recognizer[StatusLabel]
"""识别上锁与弃用状态的识别器类型别名，返回 StatusLabel 标签"""

AttributeRecognizer = Recognizer[str]
"""识别属性文本的识别器类型别名，返回字符串标签"""


def prepare_recognizer(profile: RecognitionProfile[LabelT]) -> Recognizer[LabelT]:
    """构造并返回一个识别器实例，并加载其模板。"""
    recognizer = Recognizer(profile)
    recognizer.load_templates()
    return recognizer


@lru_cache()
def prepare_status_recognizer() -> StatusRecognizer:
    return prepare_recognizer(build_status_profile())


@lru_cache()
def prepare_attribute_recognizer() -> AttributeRecognizer:
    return prepare_recognizer(build_attribute_profile())


__all__ = [
    "LabelT",
    "AttributeRecognizer",
    "StatusRecognizer",
    "TemplateDescriptor",
    "RecognitionProfile",
    "Recognizer",
    "StatusLabel",
    "prepare_recognizer",
    "prepare_status_recognizer",
    "prepare_attribute_recognizer",
]
