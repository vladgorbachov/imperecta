"""DB-free tests for movers display-currency conversion."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.modules.currency.display_converter import CurrencyConverter, _Rate
from app.modules.visualisation_calc.movements.schemas import MoverItem
from app.modules.visualisation_calc.movements.service import apply_display_currency


def _eur_converter() -> CurrencyConverter:
    return CurrencyConverter(
        rates={
            "EUR": _Rate(to_eur=1.0, to_usd=1.1),
            "USD": _Rate(to_eur=0.90909091, to_usd=1.0),
            "PLN": _Rate(to_eur=0.23, to_usd=0.253),
        },
        usd_per_eur=1.1,
    )


def _mover_item(
    *,
    old_price: Decimal | None = Decimal("100.00"),
    new_price: Decimal = Decimal("120.00"),
    currency: str = "EUR",
    marketplace_domain: str | None = "shop.de",
    country_code: str = "DE",
) -> MoverItem:
    return MoverItem(
        product_name="Widget",
        marketplace_name="Example Shop",
        marketplace_domain=marketplace_domain,
        country_code=country_code,
        old_price=old_price,
        new_price=new_price,
        currency=currency,
        price_change_pct=Decimal("20.0"),
        direction="up",
        changed_at=datetime(2026, 6, 17, 12, 0, tzinfo=UTC),
    )


def test_apply_display_currency_eur_converts_both_prices() -> None:
    item = _mover_item(currency="USD", old_price=Decimal("110.00"), new_price=Decimal("121.00"))
    apply_display_currency([item], _eur_converter(), "EUR")

    assert item.old_price == Decimal("110.00")
    assert item.new_price == Decimal("121.00")
    assert item.currency == "USD"
    assert item.display_currency == "EUR"
    assert item.conversion_available is True
    assert item.display_old_price == Decimal("100.00")
    assert item.display_new_price == Decimal("110.00")


def test_apply_display_currency_usd_mode() -> None:
    item = _mover_item(currency="EUR", old_price=Decimal("100.00"), new_price=Decimal("110.00"))
    apply_display_currency([item], _eur_converter(), "USD")

    assert item.display_currency == "USD"
    assert item.conversion_available is True
    assert item.display_old_price == Decimal("110.00")
    assert item.display_new_price == Decimal("121.00")


def test_apply_display_currency_local_mode_matches_parsed_currency() -> None:
    item = _mover_item(
        currency="EUR",
        marketplace_domain="shop.de",
        country_code="DE",
        old_price=Decimal("50.00"),
        new_price=Decimal("60.00"),
    )
    apply_display_currency([item], _eur_converter(), "local")

    assert item.display_currency == "EUR"
    assert item.conversion_available is True
    assert item.display_old_price == Decimal("50.00")
    assert item.display_new_price == Decimal("60.00")
    assert item.local_currency_resolution is not None
    assert item.local_currency_resolution.currency == "EUR"
    assert item.local_currency_unavailable is False


def test_apply_display_currency_no_rate_is_honest() -> None:
    item = _mover_item(currency="XYZ", old_price=Decimal("10.00"), new_price=Decimal("12.00"))
    apply_display_currency([item], _eur_converter(), "EUR")

    assert item.conversion_available is False
    assert item.display_old_price is None
    assert item.display_new_price is None
    assert item.display_currency is None


def test_apply_display_currency_old_price_none_leaves_display_old_none() -> None:
    item = _mover_item(old_price=None, new_price=Decimal("120.00"), currency="EUR")
    apply_display_currency([item], _eur_converter(), "EUR")

    assert item.display_old_price is None
    assert item.display_new_price == Decimal("120.00")
    assert item.conversion_available is True
