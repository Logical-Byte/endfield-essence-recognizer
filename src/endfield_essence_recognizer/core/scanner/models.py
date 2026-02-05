from dataclasses import dataclass, field
from enum import StrEnum

from endfield_essence_recognizer.core.recognition import (
    AbandonStatusLabel,
    LockStatusLabel,
)


class EssenceQuality(StrEnum):
    """Enumeration of identified essence qualities."""

    TREASURE = "treasure"
    """Identified as a valuable item based on user settings."""

    TRASH = "trash"
    """Identified as junk or unwanted item."""


@dataclass
class EssenceData:
    """Raw recognition data for a single essence."""

    stats: list[str | None]
    """List of identified attribute IDs on the essence."""

    levels: list[int | None]
    """List of identified attribute levels/enhancement values."""

    abandon_label: AbandonStatusLabel
    """The identified 'abandon' (deprecate) button state."""

    lock_label: LockStatusLabel
    """The identified 'lock' button state."""


@dataclass
class EvaluationResult:
    """The judgement result of an essence after evaluation against user settings."""

    quality: EssenceQuality
    """The overall judged quality (Treasure or Trash)."""

    log_message: str
    """The formatted log message to show to the user (contains color tags)."""

    matched_weapons: set[str] = field(default_factory=set)
    """Set of weapon IDs that this essence is suitable for."""

    is_high_level: bool = False
    """Whether any attribute on the essence exceeded a high-level threshold."""
