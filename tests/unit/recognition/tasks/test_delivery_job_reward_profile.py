from endfield_essence_recognizer.core.recognition.tasks.delivery_job_reward import (
    DeliveryJobRewardLabel,
    build_delivery_job_reward_profile,
)


def test_build_delivery_job_reward_profile():
    """
    Test that the delivery job reward profile is built correctly.
    """
    profile = build_delivery_job_reward_profile()

    assert profile.high_threshold == 0.8
    assert profile.low_threshold == 0.8

    labels = [t.label for t in profile.templates]
    assert DeliveryJobRewardLabel.WULING_DISPATCH_TICKET in labels
    assert len(profile.templates) == 1

    # Check that the path is actually a Traversable/Path pointing to the right filename
    ticket_template = profile.templates[0]
    assert ticket_template.label == DeliveryJobRewardLabel.WULING_DISPATCH_TICKET
    assert "抢单报酬_武陵调度券.png" in str(ticket_template.path)
