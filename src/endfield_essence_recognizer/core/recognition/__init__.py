from functools import lru_cache

from endfield_essence_recognizer.game_data.static_game_data import StaticGameData

from .brightness_detector import (
    BrightnessDetector,
    BrightnessDetectorProfile,
)
from .hue_recognizer import (
    ColorDescriptor,
    HueRecognitionProfile,
    HueRecognizer,
)
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
from .tasks.delivery_job_reward import (
    DeliveryJobRewardLabel,
    build_delivery_job_reward_profile,
)
from .tasks.delivery_ui import (
    DeliverySceneLabel,
    build_delivery_scene_profile,
)
from .tasks.essence_rarity import (
    RarityLabel,
    build_rarity_profile,
)
from .tasks.ui import (
    UISceneLabel,
    build_ui_scene_profile,
)
from .template_recognizer import (
    RecognitionProfile,
    TemplateDescriptor,
    TemplateRecognizer,
)

# type aliases for recognizers

type AttributeRecognizer = TemplateRecognizer[str]
"""识别属性文本的识别器类型别名，返回字符串标签"""

type AbandonStatusRecognizer = TemplateRecognizer[AbandonStatusLabel]
"""识别弃用状态的识别器类型别名，返回 AbandonStatusLabel 标签"""

type LockStatusRecognizer = TemplateRecognizer[LockStatusLabel]
"""识别上锁状态的识别器类型别名，返回 LockStatusLabel 标签"""

type UISceneRecognizer = TemplateRecognizer[UISceneLabel]
"""识别UI场景的识别器类型别名，返回 UISceneLabel 标签"""

type DeliverySceneRecognizer = TemplateRecognizer[DeliverySceneLabel]
"""识别派遣场景的识别器类型别名，返回 DeliverySceneLabel 标签"""

type DeliveryJobRewardRecognizer = TemplateRecognizer[DeliveryJobRewardLabel]
"""识别派遣奖励的识别器类型别名，返回 DeliveryJobRewardLabel 标签"""

type RarityRecognizer = HueRecognizer[RarityLabel]
"""识别基质稀有度的识别器类型别名 (基于颜色)"""

# Factory functions


def prepare_recognizer[LabelT](
    name: str, profile: RecognitionProfile[LabelT]
) -> TemplateRecognizer[LabelT]:
    """构造并返回一个识别器实例，并加载其模板。"""
    recognizer = TemplateRecognizer(name, profile)
    recognizer.load_templates()
    return recognizer


@lru_cache
def prepare_attribute_recognizer(
    static_game_data: StaticGameData,
) -> AttributeRecognizer:
    return prepare_recognizer(
        "AttributeRecognizer", build_attribute_profile(static_game_data)
    )


@lru_cache
def prepare_abandon_status_recognizer() -> AbandonStatusRecognizer:
    return prepare_recognizer("AbandonStatusRecognizer", build_abandon_status_profile())


@lru_cache
def prepare_lock_status_recognizer() -> LockStatusRecognizer:
    return prepare_recognizer("LockStatusRecognizer", build_lock_status_profile())


@lru_cache
def prepare_ui_scene_recognizer() -> UISceneRecognizer:
    return prepare_recognizer("UISceneRecognizer", build_ui_scene_profile())


@lru_cache
def prepare_delivery_scene_recognizer() -> DeliverySceneRecognizer:
    return prepare_recognizer("DeliverySceneRecognizer", build_delivery_scene_profile())


@lru_cache
def prepare_delivery_job_reward_recognizer() -> DeliveryJobRewardRecognizer:
    return prepare_recognizer(
        "DeliveryJobRewardRecognizer", build_delivery_job_reward_profile()
    )


@lru_cache
def prepare_attribute_level_recognizer() -> AttributeLevelRecognizer:
    return AttributeLevelRecognizer(
        "AttributeLevelRecognizer", build_attribute_level_recognizer_profile()
    )


@lru_cache
def prepare_rarity_recognizer() -> RarityRecognizer:
    """构造并返回一个稀有度识别器实例。"""
    return HueRecognizer("RarityRecognizer", build_rarity_profile())


__all__ = [
    "AbandonStatusLabel",
    "AbandonStatusRecognizer",
    "AttributeLevelRecognizer",
    "AttributeRecognizer",
    "BrightnessDetector",
    "BrightnessDetectorProfile",
    "ColorDescriptor",
    "DeliveryJobRewardLabel",
    "DeliveryJobRewardRecognizer",
    "DeliverySceneLabel",
    "DeliverySceneRecognizer",
    "HueRecognitionProfile",
    "HueRecognizer",
    "LockStatusLabel",
    "LockStatusRecognizer",
    "RarityLabel",
    "RarityRecognizer",
    "RecognitionProfile",
    "TemplateDescriptor",
    "TemplateRecognizer",
    "UISceneLabel",
    "UISceneRecognizer",
    "prepare_abandon_status_recognizer",
    "prepare_attribute_level_recognizer",
    "prepare_attribute_recognizer",
    "prepare_delivery_job_reward_recognizer",
    "prepare_delivery_scene_recognizer",
    "prepare_lock_status_recognizer",
    "prepare_rarity_recognizer",
    "prepare_recognizer",
    "prepare_ui_scene_recognizer",
]
