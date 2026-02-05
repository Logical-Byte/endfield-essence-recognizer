import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Mock winsound for testing on non-Windows systems or to avoid playing sound
sys.modules["winsound"] = MagicMock()

from endfield_essence_recognizer.services.audio_service import (  # noqa: E402
    AudioService,
    AudioServiceProfile,
    SoundPlayer,
    SoundResource,
    build_audio_service_profile,
)


def test_audio_service_profile_files_exist():
    """Test that default profile paths point to existing files."""
    profile = build_audio_service_profile()

    # Check enable sound
    assert profile.enable_sound.path.joinpath().exists(), (  # type: ignore
        f"Enable sound file does not exist at {profile.enable_sound.path}"
    )

    # Check disable sound
    assert profile.disable_sound.path.joinpath().exists(), (  # type: ignore
        f"Disable sound file does not exist at {profile.disable_sound.path}"
    )


@patch("endfield_essence_recognizer.services.audio_service.winsound")
def test_audio_service_play_enable(mock_winsound):
    """Test that play_enable calls winsound.PlaySound with correct data."""
    # Create a dummy file for testing
    mock_path = MagicMock(spec=Path)
    mock_path.read_bytes.return_value = b"fake_wav_data"

    profile = AudioServiceProfile(
        enable_sound=SoundResource(path=mock_path),
        disable_sound=SoundResource(path=mock_path),
    )

    service = AudioService(profile)
    service.play_enable()

    mock_winsound.PlaySound.assert_called_once()
    args, _ = mock_winsound.PlaySound.call_args
    assert args[0] == b"fake_wav_data"


@patch("endfield_essence_recognizer.services.audio_service.winsound")
def test_audio_service_play_disable(mock_winsound):
    """Test that play_enable calls winsound.PlaySound with correct data."""
    # Create a dummy file for testing
    mock_path = MagicMock(spec=Path)
    mock_path.read_bytes.return_value = b"fake_wav_data"

    profile = AudioServiceProfile(
        enable_sound=SoundResource(path=mock_path),
        disable_sound=SoundResource(path=mock_path),
    )

    service = AudioService(profile)
    service.play_disable()

    mock_winsound.PlaySound.assert_called_once()
    args, _ = mock_winsound.PlaySound.call_args
    assert args[0] == b"fake_wav_data"


@patch("endfield_essence_recognizer.services.audio_service.logger")
def test_sound_player_missing_resource(mock_logger):
    """Test that SoundPlayer handles missing resource gracefully."""
    mock_path = MagicMock(spec=Path)
    mock_path.read_bytes.side_effect = FileNotFoundError("File not found")

    resource = SoundResource(path=mock_path)

    # Initialization should log warning but not raise
    player = SoundPlayer(resource)

    mock_logger.warning.assert_called()
    assert "Failed to load sound resource" in mock_logger.warning.call_args[0][0]

    # Play should log warning but not raise
    player.play()

    assert (
        "Cannot play sound, resource not loaded" in mock_logger.warning.call_args[0][0]
    )


@patch("endfield_essence_recognizer.services.audio_service.logger")
@patch("endfield_essence_recognizer.services.audio_service.winsound")
def test_sound_player_play_error(mock_winsound, mock_logger):
    """Test that play handles unexpected errors gracefully."""
    mock_path = MagicMock(spec=Path)
    mock_path.read_bytes.return_value = b"data"

    resource = SoundResource(path=mock_path)
    # player = SoundPlayer(resource) # Start the player not needed, we use service

    # Mock winsound to raise exception
    mock_winsound.PlaySound.side_effect = Exception("Audio device error")

    profile = AudioServiceProfile(enable_sound=resource, disable_sound=resource)
    service = AudioService(profile)

    service.play_enable()

    mock_logger.error.assert_called()
    assert "Failed to play sound" in mock_logger.error.call_args[0][0]
