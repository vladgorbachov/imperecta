"""Scraping engine for marketplace price collection."""

from app.scrapers.base import AbstractScraper, ScrapedData
from app.scrapers.generic_web import GenericWebScraper
from app.scrapers.ozon import OzonScraper
from app.scrapers.wildberries import WildberriesScraper

__all__ = [
    "AbstractScraper",
    "ScrapedData",
    "OzonScraper",
    "WildberriesScraper",
    "GenericWebScraper",
]
