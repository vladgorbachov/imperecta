"""FIAT currency domain logic (scrape/ingestion path)."""

from app.modules.currency.price_eur_resolver import resolve_price_eur

__all__ = ["resolve_price_eur"]
