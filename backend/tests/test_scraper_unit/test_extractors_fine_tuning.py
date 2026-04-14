"""Fine-tuning tests: parse_price_text (EU + CIS), currency detection, multilingual titles."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from app.modules.scraper.extractors import (
    ExtractedProduct,
    _detect_currency,
    extract_auto_detect,
    extract_from_jsonld,
    extract_from_meta_tags,
    merge_and_finalize,
    parse_currency_code,
    parse_currency_symbol,
    parse_price_text,
)


# ---------------------------------------------------------------------------
#  parse_price_text — EU + CIS number formats
# ---------------------------------------------------------------------------

class TestParsePriceTextEurope:
    """European number formats (dot=thousands, comma=decimal)."""

    def test_german_format(self):
        assert parse_price_text("1.234,56 €") == 1234.56

    def test_german_no_space(self):
        assert parse_price_text("1.234,56€") == 1234.56

    def test_french_space_thousands(self):
        assert parse_price_text("1 234,56 €") == 1234.56

    def test_spanish_format(self):
        assert parse_price_text("1.234,56") == 1234.56

    def test_italian_large(self):
        assert parse_price_text("12.345,67 €") == 12345.67

    def test_euro_integer(self):
        assert parse_price_text("1.234 €") == 1234.0

    def test_small_eu_price(self):
        assert parse_price_text("9,99 €") == 9.99

    def test_eu_single_decimal(self):
        assert parse_price_text("12,5 €") == 12.5


class TestParsePriceTextAngloSaxon:
    """US/UK number formats (comma=thousands, dot=decimal)."""

    def test_us_format(self):
        assert parse_price_text("$1,234.56") == 1234.56

    def test_uk_pounds(self):
        assert parse_price_text("£1,234.56") == 1234.56

    def test_plain_decimal(self):
        assert parse_price_text("49.99") == 49.99

    def test_us_large(self):
        assert parse_price_text("$12,345.67") == 12345.67


class TestParsePriceTextCIS:
    """CIS formats: spaces as thousands, comma as decimal."""

    def test_russian_ruble(self):
        assert parse_price_text("1 299,50 ₽") == 1299.50

    def test_ukrainian_hryvnia(self):
        assert parse_price_text("1 234,56 ₴") == 1234.56

    def test_kazakh_tenge(self):
        assert parse_price_text("15 000 ₸") == 15000.0

    def test_russian_large_no_decimal(self):
        assert parse_price_text("125 000 руб") == 125000.0

    def test_belarusian_ruble(self):
        assert parse_price_text("1 234,56 Br") == 1234.56

    def test_uzbek_sum(self):
        assert parse_price_text("1 500 000") == 1500000.0

    def test_nbsp_thousands(self):
        assert parse_price_text("1\u00a0299,50\u00a0₴") == 1299.50

    def test_thin_space(self):
        assert parse_price_text("1\u2009234,56") == 1234.56


class TestParsePriceTextEdgeCases:
    """Edge cases and robustness."""

    def test_empty_string(self):
        assert parse_price_text("") is None

    def test_none_input(self):
        assert parse_price_text(None) is None  # type: ignore[arg-type]

    def test_no_digits(self):
        assert parse_price_text("no price here") is None

    def test_zero(self):
        assert parse_price_text("0,00") is None

    def test_negative_stripped(self):
        # Minus sign is stripped during cleaning; absolute value is returned.
        assert parse_price_text("-5.00") == 5.0

    def test_integer_only(self):
        assert parse_price_text("1234") == 1234.0

    def test_comma_thousands_only(self):
        # "1,234,567" — commas are thousands.
        assert parse_price_text("1,234,567") == 1234567.0

    def test_dot_thousands_only(self):
        # "1.234.567" — dots are thousands.
        assert parse_price_text("1.234.567") == 1234567.0


# ---------------------------------------------------------------------------
#  parse_currency_symbol / parse_currency_code
# ---------------------------------------------------------------------------

class TestCurrencyDetection:

    def test_euro_symbol(self):
        assert parse_currency_symbol("1.234,56 €") == "EUR"

    def test_dollar_symbol(self):
        assert parse_currency_symbol("$49.99") == "USD"

    def test_hryvnia_symbol(self):
        assert parse_currency_symbol("1 299 ₴") == "UAH"

    def test_ruble_symbol(self):
        assert parse_currency_symbol("5 000 ₽") == "RUB"

    def test_zloty_symbol(self):
        assert parse_currency_symbol("99,99 zł") == "PLN"

    def test_lira_symbol(self):
        assert parse_currency_symbol("1.234 ₺") == "TRY"

    def test_tenge_symbol(self):
        assert parse_currency_symbol("15 000 ₸") == "KZT"

    def test_code_rub(self):
        assert parse_currency_code("1 299 руб") == "RUB"

    def test_code_grn(self):
        assert parse_currency_code("1 299 грн") == "UAH"

    def test_code_tenge(self):
        assert parse_currency_code("15 000 тенге") == "KZT"

    def test_code_byn(self):
        assert parse_currency_code("price 100 byn") == "BYN"

    def test_code_pln(self):
        assert parse_currency_code("99.99 pln") == "PLN"

    def test_code_try_tl(self):
        assert parse_currency_code("1234 tl") == "TRY"

    def test_code_mdl(self):
        assert parse_currency_code("500 mdl") == "MDL"

    def test_detect_currency_combined(self):
        assert _detect_currency("1 234,56 ₴") == "UAH"
        assert _detect_currency("99.99 pln") == "PLN"
        assert _detect_currency("no currency") is None


# ---------------------------------------------------------------------------
#  Multilingual title extraction (JSON-LD + meta)
# ---------------------------------------------------------------------------

_JSONLD_TEMPLATE = """
<html><head>
<script type="application/ld+json">
{{
  "@type": "Product",
  "name": "{title}",
  "offers": {{
    "@type": "Offer",
    "price": "{price}",
    "priceCurrency": "{currency}"
  }}
}}
</script>
</head><body></body></html>
"""


class TestMultilingualTitle:

    @pytest.mark.parametrize(
        "title,price,currency",
        [
            ("Смартфон Samsung Galaxy A54", "12999", "UAH"),
            ("Ноутбук ASUS VivoBook 15", "45000", "RUB"),
            ("Kühlschrank Bosch Serie 4", "599.99", "EUR"),
            ("Téléviseur LG OLED 55C3", "1299.99", "EUR"),
            ("Televizor Samsung UE50", "2499.99", "RON"),
            ("Bulaşık Makinesi Arçelik", "8999", "TRY"),
            ("Пылесос Xiaomi Mi Robot", "150000", "KZT"),
            ("Mașină de spălat Whirlpool", "1599", "MDL"),
        ],
    )
    def test_jsonld_multilingual(self, title, price, currency):
        html = _JSONLD_TEMPLATE.format(title=title, price=price, currency=currency)
        soup = BeautifulSoup(html, "html.parser")
        ep = extract_from_jsonld(soup)
        assert ep.title == title
        assert ep.price is not None
        assert ep.currency == currency


class TestMetaTagCurrencyDetection:

    def test_meta_price_with_symbol_in_content(self):
        html = """<html><head>
        <meta property="og:title" content="Laptop ASUS" />
        <meta property="product:price:amount" content="1 299,50" />
        </head><body></body></html>"""
        soup = BeautifulSoup(html, "html.parser")
        ep = extract_from_meta_tags(soup)
        assert ep.price == 1299.50
        assert ep.title == "Laptop ASUS"

    def test_auto_detect_with_rub_symbol(self):
        html = """<html><head><title>Товар</title></head><body>
        <h1>Пылесос Xiaomi</h1>
        <span class="price">12 499 ₽</span>
        </body></html>"""
        soup = BeautifulSoup(html, "html.parser")
        ep = extract_auto_detect(soup)
        assert ep.price == 12499.0
        assert ep.currency == "RUB"
        assert ep.title == "Пылесос Xiaomi"


# ---------------------------------------------------------------------------
#  currency_raw field propagation
# ---------------------------------------------------------------------------

class TestCurrencyRawField:

    def test_jsonld_currency_raw_populated(self):
        html = _JSONLD_TEMPLATE.format(title="Test", price="99.99", currency="UAH")
        soup = BeautifulSoup(html, "html.parser")
        ep = extract_from_jsonld(soup)
        assert ep.currency_raw is not None
        assert ep.currency == "UAH"

    def test_merge_preserves_currency_raw(self):
        html = _JSONLD_TEMPLATE.format(title="Merged", price="50", currency="EUR")
        soup = BeautifulSoup(html, "html.parser")
        merged = merge_and_finalize(
            soup,
            "https://example.com/p/1",
            extract_from_jsonld(soup),
            extract_from_meta_tags(soup),
        )
        assert merged.currency_raw is not None
