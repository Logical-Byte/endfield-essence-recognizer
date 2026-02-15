"""
Provides ScannerContext dataclass to hold Recognizers for the scanner.
"""

from dataclasses import dataclass

from endfield_essence_recognizer.core.recognition import (
    AbandonStatusRecognizer,
    AttributeLevelRecognizer,
    AttributeRecognizer,
    LockStatusRecognizer,
    RarityRecognizer,
    UISceneRecognizer,
    prepare_abandon_status_recognizer,
    prepare_attribute_level_recognizer,
    prepare_attribute_recognizer,
    prepare_lock_status_recognizer,
    prepare_rarity_recognizer,
    prepare_ui_scene_recognizer,
)
from endfield_essence_recognizer.game_data.static_game_data import StaticGameData

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
    rarity_recognizer: RarityRecognizer
    ui_scene_recognizer: UISceneRecognizer
    static_game_data: StaticGameData


def build_scanner_context(static_game_data: StaticGameData) -> ScannerContext:
    """
    Builds and returns a ScannerContext with prepared Recognizers.
    """
    return ScannerContext(
        attr_recognizer=prepare_attribute_recognizer(static_game_data),
        attr_level_recognizer=prepare_attribute_level_recognizer(),
        abandon_status_recognizer=prepare_abandon_status_recognizer(),
        lock_status_recognizer=prepare_lock_status_recognizer(),
        rarity_recognizer=prepare_rarity_recognizer(),
        ui_scene_recognizer=prepare_ui_scene_recognizer(),
        static_game_data=static_game_data,
    )
