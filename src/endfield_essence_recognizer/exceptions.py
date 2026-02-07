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
