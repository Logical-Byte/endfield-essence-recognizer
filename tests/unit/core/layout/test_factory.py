import pytest

from endfield_essence_recognizer.core.layout.factory import (
    build_resolution_profile_strict,
)
from endfield_essence_recognizer.core.layout.res_1080p import Resolution1080p
from endfield_essence_recognizer.core.layout.scalable import ScalableResolutionProfile


class TestResolutionProfileFactory:
    def test_build_strict_1080p_exact(self):
        profile = build_resolution_profile_strict(1920, 1080)
        assert isinstance(profile, Resolution1080p)
        assert profile.RESOLUTION == (1920, 1080)

    def test_build_strict_2k_scaled(self):
        profile = build_resolution_profile_strict(2560, 1440)
        assert isinstance(profile, ScalableResolutionProfile)
        assert profile.RESOLUTION == (2560, 1440)

        # Test caching
        profile2 = build_resolution_profile_strict(2560, 1440)
        assert profile is profile2

    def test_build_strict_unsupported_ratio(self):
        # 16:10 resolution
        profile = build_resolution_profile_strict(1920, 1200)
        assert profile is None

    def test_build_strict_invalid_dimensions(self):
        with pytest.raises(ValueError):
            build_resolution_profile_strict(0, 0)
        with pytest.raises(ValueError):
            build_resolution_profile_strict(-1920, 1080)
