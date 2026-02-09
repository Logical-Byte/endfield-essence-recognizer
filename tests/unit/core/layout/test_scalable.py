import pytest

from endfield_essence_recognizer.core.layout.base import Point, Region
from endfield_essence_recognizer.core.layout.res_1080p import Resolution1080p
from endfield_essence_recognizer.core.layout.scalable import ScalableResolutionProfile


class TestScalableResolutionProfile:
    def test_init_invalid_dimensions(self):
        ref = Resolution1080p()
        with pytest.raises(ValueError, match="分辨率宽高须为正整数"):
            ScalableResolutionProfile(0, 1080, ref)
        with pytest.raises(ValueError, match="分辨率宽高须为正整数"):
            ScalableResolutionProfile(1920, -1, ref)

    def test_init_mismatched_aspect_ratio(self):
        ref = Resolution1080p()  # 16:9
        with pytest.raises(ValueError, match="仅支持与基准分辨率比例相同的分辨率"):
            ScalableResolutionProfile(1920, 1200, ref)  # 16:10

    def test_scaling_2k(self):
        ref = Resolution1080p()
        # 2K is 2560x1440 (16:9)
        # sx = 2560/1920 = 4/3, sy = 1440/1080 = 4/3
        profile = ScalableResolutionProfile(2560, 1440, ref)

        assert profile.RESOLUTION == (2560, 1440)

        # Test point scaling: DEPRECATE_BUTTON_POS (1807, 284)
        # 1807 * 4/3 = 2409.33 -> 2409
        # 284 * 4/3 = 378.66 -> 379
        assert profile.DEPRECATE_BUTTON_POS == Point(2409, 379)

        # Test region scaling: ESSENCE_UI_ROI (Point(38, 66), Point(143, 106))
        # 38 * 4/3 = 50.66 -> 51
        # 66 * 4/3 = 88
        # 143 * 4/3 = 190.66 -> 191
        # 106 * 4/3 = 141.33 -> 141
        assert profile.ESSENCE_UI_ROI == Region(Point(51, 88), Point(191, 141))

    def test_scaling_4k(self):
        ref = Resolution1080p()
        # 4K is 3840x2160 (16:9)
        # sx = 2, sy = 2
        profile = ScalableResolutionProfile(3840, 2160, ref)

        assert profile.RESOLUTION == (3840, 2160)
        assert profile.DEPRECATE_BUTTON_POS == Point(
            ref.DEPRECATE_BUTTON_POS.x * 2, ref.DEPRECATE_BUTTON_POS.y * 2
        )

        # essence_icon_x_list
        expected_x = [round(x * 2) for x in ref.essence_icon_x_list]
        assert list(profile.essence_icon_x_list) == expected_x

        # STATS_LEVEL_ICON_POINTS
        expected_points = [
            [Point(round(p.x * 2), round(p.y * 2)) for p in row]
            for row in ref.STATS_LEVEL_ICON_POINTS
        ]
        assert profile.STATS_LEVEL_ICON_POINTS == expected_points
