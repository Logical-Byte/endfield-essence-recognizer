"""
Loads and plays audio resources for notifications.

This is an easy single-file implementation using the `winsound` module.
"""

import importlib.resources
import winsound
from dataclasses import dataclass
from importlib.abc import Traversable
from pathlib import Path

from endfield_essence_recognizer.utils.log import logger


@dataclass(frozen=True)
class SoundResource:
    """Describes a sound resource."""

    path: Path | Traversable


@dataclass(frozen=True)
class AudioServiceProfile:
    """Configuration profile for AudioService."""

    enable_sound: SoundResource
    disable_sound: SoundResource


def build_audio_service_profile() -> AudioServiceProfile:
    """Builds the default AudioServiceProfile with hardcoded paths."""
    return AudioServiceProfile(
        enable_sound=SoundResource(
            importlib.resources.files("endfield_essence_recognizer")
            / "sounds/enable.wav"
        ),
        disable_sound=SoundResource(
            importlib.resources.files("endfield_essence_recognizer")
            / "sounds/disable.wav"
        ),
    )


class SoundPlayer:
    """
    A specific player that manages a single sound resource.

    It plays audio directly from the file system to support asynchronous playback.
    Note: Combining SND_MEMORY with SND_ASYNC can cause RuntimeErrors, so we
    use SND_FILENAME | SND_ASYNC and do not cache audio data in memory.
    """

    def __init__(self, resource: SoundResource) -> None:
        self._resource = resource
        try:
            with importlib.resources.as_file(resource.path) as file_path:
                if not file_path.exists():
                    logger.warning(f"Sound resource not found: {file_path}")
        except Exception as e:
            logger.error(
                f"Unexpected error checking sound resource {resource.path}: {e}"
            )

    def play(self) -> None:
        """Play the sound. Raises exception on failure."""
        # Ensure the resource is available as a file on the filesystem
        with importlib.resources.as_file(self._resource.path) as file_path:
            if not file_path.exists():
                logger.warning(f"Cannot play sound, file not found: {file_path}")
                return

            winsound.PlaySound(
                str(file_path), winsound.SND_FILENAME | winsound.SND_ASYNC
            )


class AudioService:
    """
    Service for handling audio playback.
    """

    def __init__(self, profile: AudioServiceProfile) -> None:
        self._enable_player = SoundPlayer(profile.enable_sound)
        self._disable_player = SoundPlayer(profile.disable_sound)

    def play_enable(self) -> None:
        """Play the enable notification sound."""
        logger.debug("Playing enable sound")
        self._safe_play(self._enable_player)

    def play_disable(self) -> None:
        """Play the disable notification sound."""
        logger.debug("Playing disable sound")
        self._safe_play(self._disable_player)

    def _safe_play(self, player: SoundPlayer) -> None:
        try:
            player.play()
        except Exception as e:
            logger.error(f"Failed to play sound: {e}")
