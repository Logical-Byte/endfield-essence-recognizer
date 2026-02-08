import numpy as np

from endfield_essence_recognizer.core.layout.base import Point, Region
from endfield_essence_recognizer.core.window.adapter import InMemoryImageSource


def test_in_memory_image_source_full_screenshot():
    # Create a 100x200 BGR image (H=100, W=200)
    img = np.zeros((100, 200, 3), dtype=np.uint8)
    img[0, 0] = [1, 2, 3]

    source = InMemoryImageSource(img)

    assert source.get_client_size() == (200, 100)

    # Full screenshot should return the same object (view/ref)
    screenshot = source.screenshot()
    assert np.array_equal(screenshot, img)
    assert screenshot.shape == (100, 200, 3)


def test_in_memory_image_source_region_screenshot():
    # Create a 100x100 BGR image
    img = np.arange(100 * 100 * 3, dtype=np.uint8).reshape((100, 100, 3))

    source = InMemoryImageSource(img)

    # Define a region from (10, 20) to (30, 40)
    region = Region(p0=Point(10, 20), p1=Point(30, 40))

    screenshot = source.screenshot(region)

    # Shape should be (height, width) -> (40-20, 30-10) -> (20, 20)
    assert screenshot.shape == (20, 20, 3)

    # Verify content matches expected slice
    expected = img[20:40, 10:30]
    assert np.array_equal(screenshot, expected)


def test_in_memory_image_source_cache_from():
    class MockSource:
        def screenshot(self, relative_region: Region | None = None):
            return np.ones((50, 50, 3), dtype=np.uint8)

        def get_client_size(self):
            return (50, 50)

        @classmethod
        def cache_from(cls, other):
            return cls()

    mock_source = MockSource()
    source = InMemoryImageSource.cache_from(mock_source)

    assert source.get_client_size() == (50, 50)
    assert np.all(source.screenshot() == 1)


def test_in_memory_image_source_cache_from_self():
    # Test caching from another InMemoryImageSource
    img = np.ones((60, 40, 3), dtype=np.uint8)
    source_a = InMemoryImageSource(img)
    source_b = InMemoryImageSource.cache_from(source_a)

    assert source_b.get_client_size() == (40, 60)
    assert np.array_equal(source_b.screenshot(), img)


def test_in_memory_image_source_view_contract():
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    source = InMemoryImageSource(img)

    screenshot = source.screenshot()

    # Since it's a view, modifying the screenshot modifies the source
    # (Checking the contract that it IS a view, though consumers shouldn't do this)
    screenshot[0, 0] = [255, 255, 255]
    assert np.array_equal(img[0, 0], [255, 255, 255])
