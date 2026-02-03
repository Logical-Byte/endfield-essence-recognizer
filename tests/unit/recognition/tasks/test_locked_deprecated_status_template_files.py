import pytest

from endfield_essence_recognizer.core.recognition.tasks.locked_deprecated_status import (
    build_abandon_status_profile,
    build_lock_status_profile,
)


def get_abandon_status_templates():
    profile = build_abandon_status_profile()
    return profile.templates


def get_lock_status_templates():
    profile = build_lock_status_profile()
    return profile.templates


@pytest.mark.parametrize(
    "template_descriptor", get_abandon_status_templates(), ids=lambda d: d.label
)
def test_abandon_status_template_file_exists(template_descriptor):
    """
    Test that each abandon status template file exists in the repository.
    """
    assert template_descriptor.path.joinpath().exists(), (
        f"Template file for {template_descriptor.label} does not exist at {template_descriptor.path}"
    )


@pytest.mark.parametrize(
    "template_descriptor", get_lock_status_templates(), ids=lambda d: d.label
)
def test_lock_status_template_file_exists(template_descriptor):
    """
    Test that each lock status template file exists in the repository.
    """
    assert template_descriptor.path.joinpath().exists(), (
        f"Template file for {template_descriptor.label} does not exist at {template_descriptor.path}"
    )
