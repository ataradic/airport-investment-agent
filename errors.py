"""Project-wide exceptions."""


class DataUnavailable(RuntimeError):
    """Raised when neither the live API nor a local cache can provide data."""
