"""ScrapeError vocabulary."""

from app.modules.scraper.errors import ScrapeError


def test_scrape_error_as_log_fragment():
    e = ScrapeError("timeout", "layer=httpx")
    assert "timeout" in e.as_log_fragment()
    assert "httpx" in e.as_log_fragment()
