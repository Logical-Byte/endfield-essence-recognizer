"""
Provides ScannerContext dataclass to hold Recognizers for the scanner.
"""

from dataclasses import dataclass

from endfield_essence_recognizer.core.recognition import (
    AbandonStatusRecognizer,
    AttributeLevelRecognizer,
    AttributeRecognizer,
    LockStatusRecognizer,
    UISceneRecognizer,
    prepare_abandon_status_recognizer,
    prepare_attribute_level_detector,
    prepare_attribute_recognizer,
    prepare_lock_status_recognizer,
    prepare_ui_scene_recognizer,
)

__all__ = ["ScannerContext"]


@dataclass
class ScannerContext:
    """
    Holds Recognizers and other context needed for the essence scanner.
    """

    attr_recognizer: AttributeRecognizer
    attr_level_recognizer: AttributeLevelRecognizer
    abandon_status_recognizer: AbandonStatusRecognizer
    lock_status_recognizer: LockStatusRecognizer
    ui_scene_recognizer: UISceneRecognizer


def build_scanner_context() -> ScannerContext:
    """
    Builds and returns a ScannerContext with prepared Recognizers.
    """
    return ScannerContext(
        attr_recognizer=prepare_attribute_recognizer(),
        attr_level_recognizer=prepare_attribute_level_detector(),
        abandon_status_recognizer=prepare_abandon_status_recognizer(),
        lock_status_recognizer=prepare_lock_status_recognizer(),
        ui_scene_recognizer=prepare_ui_scene_recognizer(),
    )
