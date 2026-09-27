import pytest

from endfield_essence_recognizer.core.layout.base import Point
from endfield_essence_recognizer.core.layout.dynamic import DynamicResolutionProfile
from endfield_essence_recognizer.core.layout.res_1080p import Resolution1080p


class TestScrollbarCheckPos:
    """滚动条检测点：逻辑坐标系下基于窗口右下角恒定锚定，不随逻辑高度缩放。"""

    def test_matches_1080p_baseline(self):
        profile = DynamicResolutionProfile(1920, 1080)
        base = Resolution1080p()
        assert profile.SCROLLBAR_CHECK_POS == base.SCROLLBAR_CHECK_POS
        assert profile.SCROLLBAR_CHECK_POS == Point(1453, 950)
        assert profile.SCROLLBAR_TOP_CHECK_POS == base.SCROLLBAR_TOP_CHECK_POS
        assert profile.SCROLLBAR_TOP_CHECK_POS == Point(1453, 130)

    def test_ultrawide_anchors_to_right_edge(self):
        # 21:9 逻辑分辨率（2560x1080）：逻辑高度仍是 1080，仅右边距需要右锚定
        profile = DynamicResolutionProfile(2560, 1080)
        assert profile.SCROLLBAR_CHECK_POS == Point(2093, 950)
        assert profile.SCROLLBAR_TOP_CHECK_POS == Point(2093, 130)

    @pytest.mark.parametrize(
        ("logical_height", "expected_bottom_y"),
        [
            (1200, 1070),  # 16:10，如 2560x1600 / 1920x1200 / 1680x1050
            (1440, 1310),  # 4:3，如 1280x960 / 1920x1440
            (1536, 1406),  # 5:4，如 1280x1024
        ],
    )
    def test_narrow_aspect_keeps_constant_margins(
        self, logical_height: int, expected_bottom_y: int
    ):
        # 窄比例分辨率逻辑宽度恒为 1920，故右边距 467、顶部边距 130 都保持恒定
        profile = DynamicResolutionProfile(1920, logical_height)
        assert profile.SCROLLBAR_CHECK_POS == Point(1453, expected_bottom_y)
        assert profile.SCROLLBAR_TOP_CHECK_POS == Point(1453, 130)

    def test_stays_inside_window(self):
        for logical_width, logical_height in [(1920, 1080), (2560, 1080), (1920, 1200)]:
            profile = DynamicResolutionProfile(logical_width, logical_height)
            for pos in (
                profile.SCROLLBAR_CHECK_POS,
                profile.SCROLLBAR_TOP_CHECK_POS,
            ):
                assert 0 <= pos.x < logical_width
                assert 0 <= pos.y < logical_height
