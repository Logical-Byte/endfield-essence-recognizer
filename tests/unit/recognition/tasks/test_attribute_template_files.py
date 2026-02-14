import os

import pytest

if os.getenv("GITHUB_ACTIONS") == "true":
    # importing endfield_essence_recognizer.core.recognition.tasks.attribute will fail in CI
    pytest.skip("Skipping test in CI environment", allow_module_level=True)

import importlib.resources

from endfield_essence_recognizer.core.recognition.tasks.attribute import (
    build_attribute_profile,
)
from endfield_essence_recognizer.game_data.static_game_data import StaticGameData


def get_attribute_templates():
    data_root = importlib.resources.files("endfield_essence_recognizer") / "data" / "v2"
    static_game_data = StaticGameData(data_root)
    profile = build_attribute_profile(static_game_data)
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
