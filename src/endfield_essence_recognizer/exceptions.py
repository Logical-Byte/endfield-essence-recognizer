"""
Custom exceptions for the endfield-essence-recognizer project.
"""


class EERError(Exception):
    """Base class for all exceptions in endfield-essence-recognizer."""

    pass


class ConfigVersionMismatchError(EERError):
    """
    Exception raised when the configuration version does not match the expected version.
    """

    def __init__(self, expected: int, got: int) -> None:
        self.expected = expected
        self.got = got
        super().__init__(f"Config version mismatch: expected {expected}, got {got}")


class WindowNotFoundError(EERError):
    """
    Exception raised when the target window is not found.
    """

    def __init__(self, window_titles: list[str], msg: str = "") -> None:
        self.window_titles = window_titles
        titles_str = ", ".join(window_titles)
        extra_msg = f" {msg}" if msg else ""
        super().__init__(
            f"Target window not found. Tried titles: {titles_str}" + extra_msg
        )


class WindowNotActiveError(EERError):
    """
    Exception raised when the target window is not active (in the foreground).
    """

    def __init__(self, window_titles: list[str], msg: str = "") -> None:
        self.window_titles = window_titles
        titles_str = ", ".join(window_titles)
        extra_msg = f" {msg}" if msg else ""
        super().__init__(
            f"Target window not active. Tried titles: {titles_str}" + extra_msg
        )


class UnsupportedResolutionError(EERError):
    """
    Exception raised when the screen resolution is unsupported.
    """

    def __init__(self, msg: str) -> None:
        super().__init__(msg)
