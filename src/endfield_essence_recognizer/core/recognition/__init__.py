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


def prepare_recognizer(profile: RecognitionProfile[LabelT]) -> Recognizer[LabelT]:
    """构造并返回一个识别器实例，并加载其模板。"""
    recognizer = Recognizer(profile)
    recognizer.load_templates()
    return recognizer


@lru_cache()
def prepare_status_recognizer() -> Recognizer[StatusLabel]:
    return prepare_recognizer(build_status_profile())


@lru_cache()
def prepare_attribute_recognizer() -> Recognizer[str]:
    return prepare_recognizer(build_attribute_profile())


__all__ = [
    "LabelT",
    "TemplateDescriptor",
    "RecognitionProfile",
    "Recognizer",
    "StatusLabel",
    "prepare_recognizer",
    "prepare_status_recognizer",
    "prepare_attribute_recognizer",
]
