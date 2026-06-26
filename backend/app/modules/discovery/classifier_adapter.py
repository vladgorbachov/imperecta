"""Thin discovery wrapper over structural page-role classification."""

from __future__ import annotations

from bs4 import BeautifulSoup

from app.modules.classifier import classify_page_role_for_discovery


def classify_page_role(soup: BeautifulSoup, base_url: str) -> str:
    """Return discovery page role via the classifier module's structural pipeline."""
    return classify_page_role_for_discovery(soup, base_url)
