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

    It loads the sound data into memory upon initialization and
    provides a method to play it.
    """

    def __init__(self, resource: SoundResource) -> None:
        self._resource = resource
        self._data: bytes | None = None
        try:
            self._data = self._load_data(resource)
        except (FileNotFoundError, OSError) as e:
            logger.warning(f"Failed to load sound resource {resource.path}: {e}")
        except Exception as e:
            logger.error(
                f"Unexpected error loading sound resource {resource.path}: {e}"
            )

    def _load_data(self, resource: SoundResource) -> bytes:
        if isinstance(resource.path, Path):
            return resource.path.read_bytes()
        elif isinstance(resource.path, Traversable):
            return resource.path.read_bytes()
        else:
            raise TypeError(f"Unsupported resource type: {type(resource.path)}")

    def play(self) -> None:
        """Play the sound. Raises exception on failure."""
        if self._data is None:
            logger.warning(
                f"Cannot play sound, resource not loaded: {self._resource.path}"
            )
            return

        winsound.PlaySound(self._data, winsound.SND_MEMORY | winsound.SND_ASYNC)


class AudioService:
    """
    Service for handling audio playback.
    """

    def __init__(self, profile: AudioServiceProfile) -> None:
        self._enable_player = SoundPlayer(profile.enable_sound)
        self._disable_player = SoundPlayer(profile.disable_sound)

    def play_enable(self) -> None:
        """Play the enable notification sound."""
        self._safe_play(self._enable_player)

    def play_disable(self) -> None:
        """Play the disable notification sound."""
        self._safe_play(self._disable_player)

    def _safe_play(self, player: SoundPlayer) -> None:
        try:
            player.play()
        except Exception as e:
            logger.error(f"Failed to play sound: {e}")
