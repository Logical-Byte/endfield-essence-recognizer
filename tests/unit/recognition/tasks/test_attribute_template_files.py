import pytest

from endfield_essence_recognizer.core.recognition.tasks.attribute import (
    build_attribute_profile,
)


def get_attribute_templates():
    profile = build_attribute_profile()
    return profile.templates


@pytest.mark.parametrize(
    "template_descriptor", get_attribute_templates(), ids=lambda d: d.label
)
@pytest.mark.skip_in_ci(
    reason="CI environment does not include json files."
    " Currently the build_attribute_profile function depends on json files."
)
def test_attribute_template_file_exists(template_descriptor):
    """
    Test that each attribute template file exists in the repository.
    """
    assert template_descriptor.path.joinpath().exists(), (
        f"Template file for {template_descriptor.label} does not exist at {template_descriptor.path}"
    )
