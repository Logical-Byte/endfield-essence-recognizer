"""
Generate layout configurations for different screen resolutions.
"""

from fractions import Fraction
from functools import lru_cache

from .base import ResolutionProfile
from .res_1080p import Resolution1080p
from .scalable import ScalableResolutionProfile

RATIO_REF_REGISTRY: dict[Fraction, ResolutionProfile] = {
    Fraction(16, 9): Resolution1080p(),
    # Only support 16:9 for now.
}


@lru_cache(maxsize=16)
def build_resolution_profile_strict(
    width: int,
    height: int,
) -> ResolutionProfile | None:
    """
    Returns a ResolutionProfile that exactly matches the given resolution.

    Args:
        width (int): 目标分辨率宽度
        height (int): 目标分辨率高度
    Returns:
        ResolutionProfile | None: 如果找到匹配的分辨率配置则返回，否则返回 None
    Raises:
        ValueError: 如果宽高非正整数
    """
    if width <= 0 or height <= 0:
        raise ValueError(
            f"Expected positive integers for width and height, got {width}x{height}"
        )
    ratio = Fraction(width, height)
    ref = RATIO_REF_REGISTRY.get(ratio, None)
    if ref is None:
        return None
    match ref.RESOLUTION:
        case (w, h) if w == width and h == height:
            return ref
        case _:
            return ScalableResolutionProfile(width, height, ref)


__all__ = [
    "build_resolution_profile_strict",
]
