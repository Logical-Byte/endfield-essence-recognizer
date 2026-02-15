import numpy as np
from loguru import logger

from endfield_essence_recognizer.core.recognition.hue_recognizer import (
    ColorDescriptor,
    HueRecognitionProfile,
    HueRecognizer,
)


def test_hue_recognizer_basic():
    # Pure Red (Hue=0), Pure Green (Hue=120)
    # BGR format
    red_descriptor = ColorDescriptor(label="red", bgr=(0, 0, 255))
    green_descriptor = ColorDescriptor(label="green", bgr=(0, 255, 0))

    profile = HueRecognitionProfile(
        descriptors=[red_descriptor, green_descriptor],
        hue_threshold_deg=20.0,
        min_saturation=50,
    )
    recognizer = HueRecognizer("TestRecognizer", profile)

    # Test Red match
    red_roi = np.zeros((10, 10, 3), dtype=np.uint8)
    red_roi[:, :] = (0, 0, 255)
    label, score = recognizer.recognize_roi(red_roi)
    assert label == "red"
    assert score > 0.99

    # Test Green match
    green_roi = np.zeros((10, 10, 3), dtype=np.uint8)
    green_roi[:, :] = (0, 255, 0)
    label, score = recognizer.recognize_roi(green_roi)
    assert label == "green"
    assert score > 0.99


def test_hue_recognizer_saturation_filter():
    # Gray color (Saturation = 0)
    gray_roi = np.zeros((10, 10, 3), dtype=np.uint8)
    gray_roi[:, :] = (128, 128, 128)

    red_descriptor = ColorDescriptor(label="red", bgr=(0, 0, 255))
    profile = HueRecognitionProfile(
        descriptors=[red_descriptor], hue_threshold_deg=20.0, min_saturation=50
    )
    recognizer = HueRecognizer("TestRecognizer", profile)

    label, score = recognizer.recognize_roi(gray_roi)
    assert label is None
    assert score == 0.0


def test_hue_recognizer_threshold():
    # Target: Red (0 deg)
    # ROI: Orange (~30 deg)
    red_descriptor = ColorDescriptor(label="red", bgr=(0, 0, 255))
    profile = HueRecognitionProfile(
        descriptors=[red_descriptor],
        hue_threshold_deg=20.0,  # 30 > 20
        min_saturation=50,
    )
    recognizer = HueRecognizer("TestRecognizer", profile)

    # Orange ROI (approx)
    # B=0, G=128, R=255 -> Hue ~ 30
    orange_roi = np.zeros((10, 10, 3), dtype=np.uint8)
    orange_roi[:, :] = (0, 128, 255)

    label, score = recognizer.recognize_roi(orange_roi)
    assert label is None
    assert score < 0.9  # Roughly 1.0 - 30/180 = 0.833


def test_hue_recognizer_circular_red():
    # Target: Red (0 deg)
    # ROI: Deep Pink/Purple (~336 deg) -> Distance = 24 deg
    red_descriptor = ColorDescriptor(label="red", bgr=(0, 0, 255))
    profile = HueRecognitionProfile(
        descriptors=[red_descriptor], hue_threshold_deg=30.0, min_saturation=50
    )
    recognizer = HueRecognizer("TestRecognizer", profile)

    # Pinkish ROI
    # B=100, G=0, R=255 -> Hue ~ 336 deg (approx)
    pink_roi = np.zeros((10, 10, 3), dtype=np.uint8)
    pink_roi[:, :] = (100, 0, 255)

    label, score = recognizer.recognize_roi(pink_roi)
    assert label == "red"
    assert score > 0.8  # 1.0 - 24/180 = 0.866


def test_hue_recognizer_fallback():
    # Red target
    red_descriptor = ColorDescriptor(label="red", bgr=(0, 0, 255))
    profile = HueRecognitionProfile(
        descriptors=[red_descriptor], hue_threshold_deg=5.0, min_saturation=50
    )
    recognizer = HueRecognizer("TestRecognizer", profile)

    # Green ROI
    green_roi = np.zeros((10, 10, 3), dtype=np.uint8)
    green_roi[:, :] = (0, 255, 0)

    label, _score = recognizer.recognize_roi_fallback(green_roi, "unknown")
    assert label == "unknown"


def test_initialization_warnings():
    # Capture loguru messages
    logs = []

    def sink(message):
        logs.append(message.record["message"])

    handler_id = logger.add(sink, level="WARNING")

    try:
        # Too close colors: 0 and 10 degrees.
        # If threshold is 30, min dist = 2 * 30 = 60 deg
        # 10 < 60 -> should warn

        c1 = ColorDescriptor(label="c1", bgr=(0, 0, 255))  # 0 deg
        c2 = ColorDescriptor(label="c2", bgr=(0, 44, 255))  # ~10 deg (approx)

        profile = HueRecognitionProfile(
            descriptors=[c1, c2], hue_threshold_deg=30.0, min_saturation=50
        )

        HueRecognizer("TestWarning", profile)
        assert any("too close" in msg for msg in logs)

        # Low saturation warning
        logs.clear()
        gray_descriptor = ColorDescriptor(label="gray", bgr=(100, 100, 100))
        low_sat_profile = HueRecognitionProfile(
            descriptors=[gray_descriptor], min_saturation=50
        )

        HueRecognizer("TestSatWarning", low_sat_profile)
        assert any("low saturation" in msg for msg in logs)
    finally:
        logger.remove(handler_id)
