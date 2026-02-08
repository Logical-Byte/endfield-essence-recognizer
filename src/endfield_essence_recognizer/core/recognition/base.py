from collections.abc import Callable
from dataclasses import dataclass, field
from importlib.abc import Traversable
from pathlib import Path

from cv2.typing import MatLike


@dataclass(frozen=True)
class TemplateDescriptor[LabelT]:
    """描述一个模板资源及其对应的标签。"""

    path: Path | Traversable
    """Path to the template image file."""
    label: LabelT
    """The label associated with this template."""


@dataclass
class RecognitionProfile[LabelT]:
    """实例化 Recognizer 所需的配置。"""

    templates: list[TemplateDescriptor[LabelT]]
    """List of template descriptors to load."""
    high_threshold: float = 0.75
    """High similarity threshold for confident matches."""
    low_threshold: float = 0.50
    """Low similarity threshold for tentative matches."""
    preprocess_roi: Callable[[MatLike], MatLike] = field(
        default_factory=lambda: lambda x: x
    )
    """Preprocessing function for ROI images."""
    preprocess_template: Callable[[MatLike], MatLike] = field(
        default_factory=lambda: lambda x: x
    )
    """Preprocessing function for template images."""
