import importlib.resources

from cv2.typing import MatLike

from endfield_essence_recognizer.core.recognition.base import (
    RecognitionProfile,
    TemplateDescriptor,
)
from endfield_essence_recognizer.utils.image import (
    linear_operation,
    to_gray_image,
)


def preprocess_text_roi(roi_image: MatLike) -> MatLike:
    """Preprocess the ROI image to enhance text recognition."""
    gray = to_gray_image(roi_image)
    enhanced = linear_operation(gray, 100, 255)
    return enhanced


def preprocess_text_template(template_image: MatLike) -> MatLike:
    """Preprocess the template image to enhance text recognition."""
    return linear_operation(template_image, 128, 255)


def build_attribute_profile() -> RecognitionProfile[str]:
    """
    Build the recognition profile for essence attributes (ATK, HP, etc.).
    """
    # We need static game data to get all possible attribute stats
    from endfield_essence_recognizer.dependencies import get_static_game_data

    static_game_data = get_static_game_data()
    all_gems = static_game_data.list_gems()
    all_gem_ids = [essence.gem_id for essence in all_gems]

    templates_dir = (
        importlib.resources.files("endfield_essence_recognizer") / "templates/generated"
    )
    # The templates are named after the essence IDs
    labels = all_gem_ids
    templates: list[TemplateDescriptor[str]] = []

    for label in labels:
        template_path = templates_dir / f"{label}.png"
        templates.append(TemplateDescriptor(path=template_path, label=label))

    return RecognitionProfile(
        templates=templates,
        high_threshold=0.75,
        low_threshold=0.50,
        # preprocess_roi=preprocess_text_roi,
        # preprocess_template=preprocess_text_template,
    )
