import pytest

from endfield_essence_recognizer.core.recognition.tasks.ui import build_ui_scene_profile


def get_ui_scene_templates():
    profile = build_ui_scene_profile()
    return profile.templates


@pytest.mark.parametrize(
    "template_descriptor", get_ui_scene_templates(), ids=lambda d: d.label
)
def test_ui_scene_template_file_exists(template_descriptor):
    """
    Test that each UI scene template file exists in the repository.
    """
    # .joinpath() on a Traversable object from importlib.resources.files()
    # is a common way to ensure it exists or to get the actual path object.
    assert template_descriptor.path.joinpath().exists(), (
        f"Template file for {template_descriptor.label} does not exist at {template_descriptor.path}"
    )
