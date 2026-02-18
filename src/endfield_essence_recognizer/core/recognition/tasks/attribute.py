import importlib.resources

from cv2.typing import MatLike

from endfield_essence_recognizer.core.recognition.template_recognizer import (
    RecognitionProfile,
    TemplateDescriptor,
)
from endfield_essence_recognizer.game_data.static_game_data import StaticGameData
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


def build_attribute_profile(
    static_game_data: StaticGameData,
) -> RecognitionProfile[str]:
    """
    Build the recognition profile for essence attributes (ATK, HP, etc.).
    """
    # We need static game data to get all possible attribute stats
    all_stats = static_game_data.list_stats()
    all_stat_ids = [s.stat_id for s in all_stats]

    templates_dir = (
        importlib.resources.files("endfield_essence_recognizer") / "templates/generated"
    )
    # The templates are named after the essence IDs
    labels = all_stat_ids
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
