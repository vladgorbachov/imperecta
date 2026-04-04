"""Structured scrape failures for pool and persistence (single vocabulary)."""


class ScrapeError(Exception):
    """Domain error with machine-readable code for scrape_logs mapping."""

    __slots__ = ("code", "detail")

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail

    def as_log_fragment(self) -> str:
        """Stable substring for service._determine_log_status heuristics."""
        return f"{self.code}:{self.detail}" if self.detail else self.code


# Canonical scrape_logs.status CHECK values (VARCHAR(50); migrations 006–007).
SCRAPE_LOG_STATUSES: tuple[str, ...] = (
    "success",
    "error",
    "timeout",
    "blocked",
    "captcha",
    "not_found",
    "price_not_found",
    "parse_error",
    "missing_critical_data",
    "technical_error",
)

# Codes aligned with scrape_logs CHECK (via mapping in service layer)
FETCH_FAILED = "fetch_failed"
TIMEOUT = "timeout"
BLOCKED = "blocked"
CAPTCHA = "captcha"
NOT_FOUND = "not_found"
PARSE_ERROR = "parse_error"
PRICE_NOT_FOUND = "price_not_found"
MISSING_CURRENCY = "missing_currency"
