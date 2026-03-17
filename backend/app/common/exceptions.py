"""Typed exception hierarchy for the application."""


class ImperectaError(Exception):
    """Base application error."""

    def __init__(self, message: str, code: str = "UNKNOWN"):
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(ImperectaError):
    pass


class DuplicateError(ImperectaError):
    pass


class QuotaExceededError(ImperectaError):
    pass


class ScraperError(ImperectaError):
    pass


class DiscoveryError(ImperectaError):
    pass


class ExternalAPIError(ImperectaError):
    pass

