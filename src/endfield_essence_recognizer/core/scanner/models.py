from dataclasses import dataclass, field
from enum import StrEnum

from endfield_essence_recognizer.core.recognition import (
    AbandonStatusLabel,
    LockStatusLabel,
)


class EssenceQuality(StrEnum):
    TREASURE = "treasure"
    TRASH = "trash"


@dataclass
class EssenceData:
    """Raw recognition data for a single essence."""

    stats: list[str | None]
    levels: list[int | None]
    abandon_label: AbandonStatusLabel
    lock_label: LockStatusLabel


@dataclass
class EvaluationResult:
    """The judgement result of an essence."""

    quality: EssenceQuality
    # The formatted log message to show to the user (contains color tags)
    log_message: str
    matched_weapons: set[str] = field(default_factory=set)
    is_high_level: bool = False
