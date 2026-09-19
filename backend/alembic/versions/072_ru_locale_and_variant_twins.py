"""Legal clean-up WP11: no Russian UI locale; ru storefront twins retired.

Revision ID: 072_ru_locale_and_variant_twins
Revises: 071_legal_purge_ru_by_kz
Create Date: 2026-09-19

1. `users.language`: the `ru` UI locale is removed from the product
   (founder's decision 2026-09-19). Rows on `ru` move to `en` (0 rows in
   prod on 2026-09-19 — both users are elsewhere) and a CHECK pins the
   column to the supported list, mirroring `common/validation.py`.

2. Storefront `/ru/` variants (WP11.4). Several MD/UA shops publish the same
   offer under the local-language URL and under `/ru/`; discovery used to
   take both. On 2026-09-19 the pool held 162 947 active `/ru/` listings, of
   which 52 545 have their local-language twin (same URL without the `/ru`
   segment, or with `/ro/`) in the same marketplace — darwin.md 16 212,
   ultra.md 36 333. Those twins are DEACTIVATED here (history kept, no
   deletion, no data loss); the local-language row carries on. `/ru/` rows
   without a twin (pandashop.md, allo.ua, most of darwin.md) stay active:
   whether a local-language page exists is only known from the page itself
   (canonical / hreflang), which the discovery rule in
   `scraper/locale_selection.py` now applies at ingest.
"""

from __future__ import annotations

from alembic import op

revision = "072_ru_locale_and_variant_twins"
down_revision = "071_legal_purge_ru_by_kz"
branch_labels = None
depends_on = None

SUPPORTED_LANGUAGES = ("en", "ar", "es", "zh", "fr", "ro", "uk")

# FactListing.compute_url_hash in SQL: sha256(strip + rstrip('/') + lower).
_URL_HASH = "encode(sha256(convert_to(lower(rtrim(btrim({url}), '/')), 'UTF8')), 'hex')"
_RU_PREFIX = r"^(https?://[^/]+)/ru/"


def upgrade() -> None:
    op.execute("SET LOCAL statement_timeout = '10min';")

    langs = ", ".join(f"'{code}'" for code in SUPPORTED_LANGUAGES)
    op.execute("UPDATE users SET language = 'en' WHERE language = 'ru' OR language LIKE 'ru-%';")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_language_supported;")
    op.execute(
        f"ALTER TABLE users ADD CONSTRAINT ck_users_language_supported "
        f"CHECK (language IN ({langs}));"
    )

    root_hash = _URL_HASH.format(url=f"regexp_replace(l.external_url, '{_RU_PREFIX}', '\\1/')")
    ro_hash = _URL_HASH.format(url=f"regexp_replace(l.external_url, '{_RU_PREFIX}', '\\1/ro/')")
    op.execute(
        f"""
        DO $ru$
        DECLARE
            n integer;
        BEGIN
            CREATE TEMP TABLE _ru_twins ON COMMIT DROP AS
            SELECT l.id
            FROM fact_listing l
            WHERE l.is_active
              AND l.external_url ~ '{_RU_PREFIX}'
              AND EXISTS (
                  SELECT 1 FROM fact_listing t
                  WHERE t.marketplace_id = l.marketplace_id
                    AND t.id <> l.id
                    AND t.url_hash IN ({root_hash}, {ro_hash})
              );
            UPDATE fact_listing SET is_active = false, updated_at = now()
            WHERE id IN (SELECT id FROM _ru_twins);
            GET DIAGNOSTICS n = ROW_COUNT;
            RAISE NOTICE 'ru storefront twins deactivated: %', n;
        END
        $ru$;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_language_supported;")
