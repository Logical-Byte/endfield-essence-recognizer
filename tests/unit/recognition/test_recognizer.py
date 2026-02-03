from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from endfield_essence_recognizer.core.recognition.base import (
    RecognitionProfile,
    TemplateDescriptor,
)
from endfield_essence_recognizer.core.recognition.recognizer import Recognizer


@pytest.fixture
def mock_template_path():
    return Path("mock/path/template.png")


@pytest.fixture
def profile(mock_template_path):
    descriptor = TemplateDescriptor(path=mock_template_path, label="test_label")
    return RecognitionProfile(
        templates=[descriptor], high_threshold=0.8, low_threshold=0.6
    )


@pytest.fixture
def recognizer(profile):
    return Recognizer(profile)


def test_load_templates(recognizer, mock_template_path):
    """Test that templates are correctly loaded and stored from the profile."""
    mock_image = np.zeros((10, 10), dtype=np.uint8)

    # Mock importlib.resources.as_file context manager
    with (
        patch("importlib.resources.as_file") as mock_as_file,
        patch(
            "endfield_essence_recognizer.core.recognition.recognizer.load_image"
        ) as mock_load_image,
    ):
        # Adjust mock for as_file which returns a context manager
        mock_as_file.return_value.__enter__.return_value = mock_template_path
        mock_load_image.return_value = mock_image

        recognizer.load_templates()

        assert "test_label" in recognizer._templates
        assert len(recognizer._templates["test_label"]) == 1
        assert np.array_equal(recognizer._templates["test_label"][0], mock_image)
        # cv2.IMREAD_GRAYSCALE value is usually 0
        mock_load_image.assert_called_once_with(
            mock_template_path, cv2.IMREAD_GRAYSCALE
        )


def test_load_templates_preprocessing(recognizer, mock_template_path):
    """Test that template preprocessing is applied during template loading."""
    mock_image = np.zeros((10, 10), dtype=np.uint8)
    mock_processed = np.ones((10, 10), dtype=np.uint8)

    # Mock preprocessor
    mock_template_preprocess = MagicMock(return_value=mock_processed)
    recognizer.profile.preprocess_template = mock_template_preprocess

    with (
        patch("importlib.resources.as_file") as mock_as_file,
        patch(
            "endfield_essence_recognizer.core.recognition.recognizer.load_image"
        ) as mock_load_image,
    ):
        mock_as_file.return_value.__enter__.return_value = mock_template_path
        mock_load_image.return_value = mock_image

        recognizer.load_templates()

        mock_template_preprocess.assert_called_once()
        assert np.array_equal(recognizer._templates["test_label"][0], mock_processed)


def test_load_templates_fail(recognizer, mock_template_path):
    """Test behavior when template image loading fails."""
    with (
        patch("importlib.resources.as_file") as mock_as_file,
        patch(
            "endfield_essence_recognizer.core.recognition.recognizer.load_image"
        ) as mock_load_image,
    ):
        mock_as_file.return_value.__enter__.return_value = mock_template_path
        mock_load_image.return_value = None  # Simulate load failure

        recognizer.load_templates()

        assert "test_label" not in recognizer._templates


def test_recognize_roi_high_score(recognizer):
    """Test recognition when a high-confidence match is found."""
    # Setup
    label = "test_label"
    template = np.ones((5, 5), dtype=np.uint8) * 255
    recognizer._templates[label] = [template]

    # ROI that fits the template
    roi = np.ones((10, 10), dtype=np.uint8) * 255

    with (
        patch("cv2.matchTemplate") as mock_match,
        patch("cv2.minMaxLoc") as mock_min_max,
    ):
        mock_match.return_value = np.array([[0.9]], dtype=np.float32)
        mock_min_max.return_value = (0, 0.9, (0, 0), (0, 0))

        res_label, score = recognizer.recognize_roi(roi)

        assert res_label == label
        assert score == 0.9


def test_recognize_roi_low_score(recognizer):
    """Test recognition when a tentative match (between low and high thresholds) is found."""
    # Setup
    label = "test_label"
    template = np.ones((5, 5), dtype=np.uint8) * 255
    recognizer._templates[label] = [template]

    roi = np.zeros((10, 10), dtype=np.uint8)

    with (
        patch("cv2.matchTemplate") as mock_match,
        patch("cv2.minMaxLoc") as mock_min_max,
    ):
        # 0.7 is between low (0.6) and high (0.8)
        mock_match.return_value = np.array([[0.7]], dtype=np.float32)
        mock_min_max.return_value = (0, 0.7, (0, 0), (0, 0))

        res_label, score = recognizer.recognize_roi(roi)

        assert res_label == label
        assert score == 0.7


def test_recognize_roi_no_match(recognizer):
    """Test recognition when no match exceeds the low threshold."""
    # Setup
    label = "test_label"
    template = np.ones((5, 5), dtype=np.uint8) * 255
    recognizer._templates[label] = [template]

    roi = np.zeros((10, 10), dtype=np.uint8)

    with (
        patch("cv2.matchTemplate") as mock_match,
        patch("cv2.minMaxLoc") as mock_min_max,
    ):
        # 0.3 is below low threshold (0.6)
        mock_match.return_value = np.array([[0.3]], dtype=np.float32)
        mock_min_max.return_value = (0, 0.3, (0, 0), (0, 0))

        res_label, score = recognizer.recognize_roi(roi)

        assert res_label is None
        assert score == 0.3


def test_recognize_roi_empty_templates(recognizer):
    """Test recognition behavior when no templates have been loaded."""
    roi = np.zeros((10, 10), dtype=np.uint8)
    res_label, score = recognizer.recognize_roi(roi)
    assert res_label is None
    assert score == 0.0


def test_recognize_roi_too_small(recognizer):
    """Test recognition when the input ROI is smaller than the template image."""
    # Setup
    label = "test_label"
    template = np.ones((10, 10), dtype=np.uint8)
    recognizer._templates[label] = [template]

    # ROI is smaller than template
    roi = np.zeros((5, 5), dtype=np.uint8)

    res_label, score = recognizer.recognize_roi(roi)

    assert res_label is None
    assert score == -1.0


def test_recognize_roi_color_conversion(recognizer):
    """Test that color ROI inputs are automatically converted to grayscale before matching."""
    label = "test_label"
    template = np.ones((5, 5), dtype=np.uint8)
    recognizer._templates[label] = [template]

    # Color ROI (H, W, C)
    roi_color = np.zeros((10, 10, 3), dtype=np.uint8)

    with (
        patch("cv2.cvtColor") as mock_cvt,
        patch("cv2.matchTemplate") as mock_match,
        patch("cv2.minMaxLoc") as mock_min_max,
    ):
        mock_cvt.return_value = np.zeros((10, 10), dtype=np.uint8)
        mock_match.return_value = np.array([[0.5]], dtype=np.float32)
        mock_min_max.return_value = (0, 0.5, (0, 0), (0, 0))

        recognizer.recognize_roi(roi_color)

        mock_cvt.assert_called_once_with(roi_color, cv2.COLOR_BGR2GRAY)


def test_recognize_roi_preprocessing(recognizer):
    """Test that ROI preprocessing is applied before recognition."""
    # Setup
    label = "test_label"
    template = np.ones((5, 5), dtype=np.uint8)
    recognizer._templates[label] = [template]

    # Mock preprocessors
    mock_roi_preprocess = MagicMock(side_effect=lambda x: x)
    recognizer.profile.preprocess_roi = mock_roi_preprocess

    roi = np.zeros((10, 10), dtype=np.uint8)

    with (
        patch("cv2.matchTemplate") as mock_match,
        patch("cv2.minMaxLoc") as mock_min_max,
    ):
        mock_match.return_value = np.array([[0.5]], dtype=np.float32)
        mock_min_max.return_value = (0, 0.5, (0, 0), (0, 0))

        recognizer.recognize_roi(roi)

        mock_roi_preprocess.assert_called_once()
