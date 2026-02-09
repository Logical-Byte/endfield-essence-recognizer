from functools import lru_cache

from endfield_essence_recognizer.core.recognition import (
    AbandonStatusRecognizer,
    AttributeLevelRecognizer,
    AttributeRecognizer,
    DeliveryJobRewardRecognizer,
    DeliverySceneRecognizer,
    LockStatusRecognizer,
    UISceneRecognizer,
    prepare_abandon_status_recognizer,
    prepare_attribute_level_recognizer,
    prepare_attribute_recognizer,
    prepare_delivery_job_reward_recognizer,
    prepare_delivery_scene_recognizer,
    prepare_lock_status_recognizer,
    prepare_ui_scene_recognizer,
)


# Though the underlying factory functions are already cached,
# still wrap these functions with lru_cache to show
# singleton semantics
@lru_cache
def get_attribute_recognizer_dep() -> AttributeRecognizer:
    """
    Get the default attribute Recognizer instance.
    """
    return prepare_attribute_recognizer()


@lru_cache
def get_attribute_level_recognizer_dep() -> AttributeLevelRecognizer:
    """
    Get the default attribute level Recognizer instance.
    """
    return prepare_attribute_level_recognizer()


@lru_cache
def get_abandon_status_recognizer_dep() -> AbandonStatusRecognizer:
    """
    Get the default abandon status Recognizer instance.
    """
    return prepare_abandon_status_recognizer()


@lru_cache
def get_lock_status_recognizer_dep() -> LockStatusRecognizer:
    """
    Get the default lock status Recognizer instance.
    """
    return prepare_lock_status_recognizer()


@lru_cache
def get_ui_scene_recognizer_dep() -> UISceneRecognizer:
    """
    Get the default UI scene Recognizer instance.
    """
    return prepare_ui_scene_recognizer()


@lru_cache
def get_delivery_scene_recognizer_dep() -> DeliverySceneRecognizer:
    """
    Get the default delivery scene Recognizer instance.
    """
    return prepare_delivery_scene_recognizer()


@lru_cache
def get_delivery_job_reward_recognizer_dep() -> DeliveryJobRewardRecognizer:
    """
    Get the default delivery job reward Recognizer instance.
    """
    return prepare_delivery_job_reward_recognizer()
