import pytest

from endfield_essence_recognizer.core.recognition.tasks.delivery_job_reward import (
    build_delivery_job_reward_profile,
)
from endfield_essence_recognizer.core.recognition.tasks.delivery_ui import (
    build_delivery_scene_profile,
)


def get_delivery_templates():
    ui_profile = build_delivery_scene_profile()
    reward_profile = build_delivery_job_reward_profile()
    return ui_profile.templates + reward_profile.templates


@pytest.mark.parametrize(
    "template_descriptor", get_delivery_templates(), ids=lambda d: f"{d.label}"
)
def test_delivery_template_file_exists(template_descriptor):
    """
    Test that each delivery template file exists in the repository.
    """
    assert template_descriptor.path.joinpath().exists(), (
        f"Template file for {template_descriptor.label} does not exist at {template_descriptor.path}"
    )
