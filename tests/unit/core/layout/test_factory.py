import pytest

from endfield_essence_recognizer.core.layout.dynamic import DynamicResolutionProfile
from endfield_essence_recognizer.core.layout.factory import (
    build_resolution_profile,
)


class TestResolutionProfileFactory:
    def test_build_1080p(self):
        profile = build_resolution_profile(1920, 1080)
        assert isinstance(profile, DynamicResolutionProfile)
        assert profile.RESOLUTION == (1920, 1080)

    def test_build_non_16_9(self):
        # 16:10 logical resolution (e.g. 1728x1080)
        profile = build_resolution_profile(1728, 1080)
        assert isinstance(profile, DynamicResolutionProfile)
        assert profile.RESOLUTION == (1728, 1080)

    def test_build_ultrawide(self):
        # 21:9 logical resolution (e.g. 2560x1080)
        profile = build_resolution_profile(2560, 1080)
        assert isinstance(profile, DynamicResolutionProfile)
        assert profile.RESOLUTION == (2560, 1080)

    def test_caching(self):
        profile1 = build_resolution_profile(1920, 1080)
        profile2 = build_resolution_profile(1920, 1080)
        assert profile1 is profile2

    def test_invalid_dimensions(self):
        with pytest.raises(ValueError):
            build_resolution_profile(0, 0)
        with pytest.raises(ValueError):
            build_resolution_profile(-1920, 1080)
