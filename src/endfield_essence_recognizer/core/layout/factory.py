"""
Generate layout configurations for different screen resolutions.
"""

from functools import lru_cache

from .base import ResolutionProfile
from .dynamic import DynamicResolutionProfile


@lru_cache(maxsize=16)
def build_resolution_profile(
    width: int,
    height: int,
) -> ResolutionProfile:
    """
    Returns a ResolutionProfile for the given logical resolution.

    Intended to be called with the logical dimensions produced by
    ``ScalingImageSource`` (height normalised to 1080).

    Args:
        width: 逻辑分辨率宽度（正整数）
        height: 逻辑分辨率高度（正整数）
    Returns:
        对应的 ResolutionProfile 实例
    Raises:
        ValueError: 如果宽高非正整数
    """
    if width <= 0 or height <= 0:
        raise ValueError(
            f"Expected positive integers for width and height, got {width}x{height}"
        )
    return DynamicResolutionProfile(width, height)


__all__ = [
    "build_resolution_profile",
]
