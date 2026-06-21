"""Read-only diagnostic harness for real scraper extract output.

Usage (from backend/):

    python -m scripts.scraper_output_harness \\
        --urls scripts/harness_urls.txt \\
        --out scripts/output

Put one product URL per line in the URLs file (# comments allowed).
Writes ``scraper_output.json`` and ``scraper_output.csv`` under --out.

Uses the same env/config as the app (fetch backends, proxy limiter). Unseeded shops
(e.g. bomba.md) use an in-memory default fetch context — no dim_marketplace row and
no DB writes. Does not call data_firewall, sign, or persist.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

from bs4 import BeautifulSoup

from app.modules.classifier import classify_page_role_for_discovery
from app.modules.persist.writer import build_fact_price_fields
from app.modules.scraper.extractors import (
    ExtractedProduct,
    extract_auto_detect,
    extract_from_jsonld,
    extract_from_meta_tags,
    extract_from_microdata,
)
from app.modules.scraper.scraper_pool import PoolScrapeResult, ScraperPool

_DEFAULT_URLS_FILE = Path(__file__).resolve().parent / "harness_urls.txt"
_DEFAULT_OUT_DIR = Path(__file__).resolve().parent / "output"
_INTER_URL_DELAY_SEC = 1.5

_ERROR_TO_HTTP_STATUS: dict[str, int | None] = {
    "not_found": 404,
    "blocked": 403,
    "timeout": None,
    "fetch_failed": None,
}


@dataclass(frozen=True)
class HarnessFetchContext:
    """In-memory fetch settings for unseeded / arbitrary product URLs."""

    requires_js: bool
    scrape_tier: int
    custom_selectors: dict[str, str] | None
    marketplace_source: str
    host: str


def _default_fetch_context(url: str) -> HarnessFetchContext:
    """Shop-agnostic defaults — never inserts into dim_marketplace."""
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return HarnessFetchContext(
        requires_js=False,
        scrape_tier=1,
        custom_selectors=None,
        marketplace_source="in_memory_default",
        host=host,
    )


def _json_safe(value: Any) -> Any:
    """Convert values to JSON-serializable forms."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    return str(value)


def _typed_value(value: Any) -> dict[str, Any]:
    """Attach python type metadata for inspection."""
    if value is None:
        return {"value": None, "python_type": "NoneType"}
    return {"value": _json_safe(value), "python_type": type(value).__name__}


def _serialize_dataclass(obj: Any) -> dict[str, dict[str, Any]]:
    """Serialize a dataclass instance with per-field types."""
    if not is_dataclass(obj):
        return {"value": _typed_value(obj)}
    return {
        field.name: _typed_value(getattr(obj, field.name))
        for field in fields(obj)
    }


def _load_urls(urls_file: Path, cli_urls: list[str] | None) -> list[str]:
    """Load URLs from CLI and/or file; skip blanks and # comments."""
    urls: list[str] = []
    if cli_urls:
        urls.extend(u.strip() for u in cli_urls if u.strip())
    if urls_file.is_file():
        for line in urls_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            urls.append(stripped)
    seen: set[str] = set()
    unique: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def _infer_http_status(fetch_error: str | None, html: str | None) -> int | None:
    """Best-effort HTTP status from pipeline error codes (status not exposed directly)."""
    if html:
        return 200
    if not fetch_error:
        return None
    return _ERROR_TO_HTTP_STATUS.get(fetch_error.lower())


def _extraction_layer_notes(html: str | None, url: str) -> dict[str, Any]:
    """Report which extractor layers surface fields (observation only)."""
    if not html:
        return {"page_role_classifier": None, "layers": {}}

    soup = BeautifulSoup(html, "html.parser")
    layer_products = {
        "jsonld": extract_from_jsonld(soup, url),
        "microdata": extract_from_microdata(soup, url),
        "meta": extract_from_meta_tags(soup, url),
        "auto": extract_auto_detect(soup, url),
    }
    layers: dict[str, Any] = {}
    for name, product in layer_products.items():
        layers[name] = {
            "has_title": product.title is not None,
            "has_price": product.price is not None,
            "has_currency": product.currency is not None,
            "has_image_url": product.image_url is not None,
        }
    return {
        "page_role_classifier": classify_page_role_for_discovery(soup, url),
        "page_role_source": "classify_page_role_for_discovery",
        "layers": layers,
    }


def _persist_fields_skip_reason(data: ExtractedProduct | None) -> str | None:
    """Explain why build_fact_price_fields would not run."""
    if data is None:
        return "no_extracted_data"
    if data.price is None:
        return "price_missing"
    if not data.currency:
        return "currency_missing"
    return None


def _build_would_be_persist_fields(
    data: ExtractedProduct | None,
) -> tuple[dict[str, dict[str, Any]] | None, str | None]:
    """Mirror ingestion.build_fact_price_fields without firewall or DB."""
    skip = _persist_fields_skip_reason(data)
    if skip is not None:
        return None, skip

    assert data is not None
    now = datetime.now(tz=timezone.utc)
    original_price_value = (
        float(data.original_price)
        if data.original_price is not None
        else None
    )
    fields_dict = build_fact_price_fields(
        listing_id=uuid4(),
        date_id=int(now.strftime("%Y%m%d")),
        price=float(data.price),  # type: ignore[arg-type]
        currency_code=str(data.currency),
        original_price=original_price_value,
        discount_pct=getattr(data, "discount_pct", None),
        price_change_pct=getattr(data, "price_change_pct", None),
        scraped_at=now,
        scrape_job_id=None,
    )
    typed = {key: _typed_value(value) for key, value in fields_dict.items()}
    return typed, None


def _serialize_pool_result(
    result: PoolScrapeResult,
    *,
    fetch_ctx: HarnessFetchContext,
    fetch_error: str | None,
    html: str | None,
    would_be_persist_fields: dict[str, dict[str, Any]] | None,
    persist_fields_skip_reason: str | None,
    extraction_notes: dict[str, Any],
) -> dict[str, Any]:
    """Full per-URL capture for JSON artifact."""
    data = result.data
    http_status = _infer_http_status(fetch_error, html)
    return {
        "url": result.url,
        "host": fetch_ctx.host,
        "marketplace_source": fetch_ctx.marketplace_source,
        "fetch_context": {
            "requires_js": fetch_ctx.requires_js,
            "scrape_tier": fetch_ctx.scrape_tier,
            "custom_selectors": fetch_ctx.custom_selectors,
        },
        "success": result.success,
        "error": result.error,
        "fetch_error": fetch_error,
        "http_status": http_status,
        "fetch_backend": result.fetch_backend,
        "duration_ms": result.duration_ms,
        "is_partial": result.is_partial,
        "is_empty": result.is_empty,
        "extracted_fields": result.extracted_fields,
        "missing_fields": result.missing_fields,
        "log_status": result.log_status,
        "page_role": result.page_role,
        "extracted_product": _serialize_dataclass(data) if data is not None else None,
        "would_be_persist_fields": would_be_persist_fields,
        "persist_fields_skip_reason": persist_fields_skip_reason,
        "extraction_notes": extraction_notes,
        "captured_at": datetime.now(tz=timezone.utc).isoformat(),
    }


def _csv_row(record: dict[str, Any]) -> dict[str, str]:
    """Flatten one JSON record for CSV scanning."""
    product = record.get("extracted_product") or {}

    def _field(name: str) -> str:
        wrapped = product.get(name) or {}
        value = wrapped.get("value")
        return "" if value is None else str(value)

    def _ptype(name: str) -> str:
        wrapped = product.get(name) or {}
        return str(wrapped.get("python_type") or "")

    image_url = _field("image_url")
    note_parts = [
        str(record.get("error") or ""),
        str(record.get("persist_fields_skip_reason") or ""),
    ]
    note = "; ".join(part for part in note_parts if part)

    return {
        "url": record.get("url") or "",
        "fetch_backend": str(record.get("fetch_backend") or ""),
        "http_status": str(record.get("http_status") if record.get("http_status") is not None else ""),
        "title": _field("title"),
        "price": _field("price"),
        "price_type": _ptype("price"),
        "currency": _field("currency"),
        "currency_raw": _field("currency_raw"),
        "page_role": str(record.get("page_role") or ""),
        "original_price": _field("original_price"),
        "image_url_present": str(bool(image_url)),
        "missing_fields": ",".join(record.get("missing_fields") or []),
        "note": note,
    }


async def _scrape_one(pool: ScraperPool, url: str) -> dict[str, Any]:
    """Run the real fetch + extract path for one URL."""
    fetch_ctx = _default_fetch_context(url)
    fetch = await pool.fetch_listing_html(
        url,
        requires_js=fetch_ctx.requires_js,
        scrape_tier=fetch_ctx.scrape_tier,
    )
    result = pool.build_scrape_result_from_html(
        fetch.html,
        url,
        custom_selectors=fetch_ctx.custom_selectors,
        used_backend=fetch.used_backend,
        duration_ms=fetch.duration_ms,
        last_error=fetch.last_error,
        scrape_tier=fetch_ctx.scrape_tier,
        requires_js=fetch_ctx.requires_js,
    )
    would_be, skip_reason = _build_would_be_persist_fields(result.data)
    notes = _extraction_layer_notes(fetch.html, url)
    return _serialize_pool_result(
        result,
        fetch_ctx=fetch_ctx,
        fetch_error=fetch.last_error if not fetch.html else None,
        html=fetch.html,
        would_be_persist_fields=would_be,
        persist_fields_skip_reason=skip_reason,
        extraction_notes=notes,
    )


async def _run_harness(urls: list[str], out_dir: Path) -> int:
    """Fetch + extract all URLs and write JSON/CSV artifacts."""
    if not urls:
        print("No URLs to process. Add URLs to the file or pass --url.", file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    pool = ScraperPool()
    records: list[dict[str, Any]] = []

    for index, url in enumerate(urls):
        if index > 0:
            await asyncio.sleep(_INTER_URL_DELAY_SEC)
        print(f"[{index + 1}/{len(urls)}] {url}")
        try:
            records.append(await _scrape_one(pool, url))
        except Exception as exc:
            records.append({
                "url": url,
                "success": False,
                "error": f"harness_error:{exc}",
                "http_status": None,
                "extracted_product": None,
                "would_be_persist_fields": None,
                "persist_fields_skip_reason": "harness_exception",
                "captured_at": datetime.now(tz=timezone.utc).isoformat(),
            })

    json_path = out_dir / "scraper_output.json"
    csv_path = out_dir / "scraper_output.csv"
    json_path.write_text(
        json.dumps(records, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    csv_fields = [
        "url",
        "fetch_backend",
        "http_status",
        "title",
        "price",
        "price_type",
        "currency",
        "currency_raw",
        "page_role",
        "original_price",
        "image_url_present",
        "missing_fields",
        "note",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields)
        writer.writeheader()
        for record in records:
            writer.writerow(_csv_row(record))

    with_price = sum(
        1
        for record in records
        if (record.get("extracted_product") or {}).get("price", {}).get("value") is not None
    )
    with_currency = sum(
        1
        for record in records
        if (record.get("extracted_product") or {}).get("currency", {}).get("value")
    )
    fetch_failures = sum(1 for record in records if not record.get("success"))
    role_counts: dict[str, int] = {}
    for record in records:
        role = str(record.get("page_role") or "unknown")
        role_counts[role] = role_counts.get(role, 0) + 1

    print()
    print(f"URLs processed: {len(records)}")
    print(f"Extracted a price: {with_price}")
    print(f"Extracted currency: {with_currency}")
    print(f"Fetch failures: {fetch_failures}")
    print("page_role breakdown:", ", ".join(f"{k}={v}" for k, v in sorted(role_counts.items())))
    print(f"JSON: {json_path}")
    print(f"CSV:  {csv_path}")
    return 0


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dump real scraper extract output for product URLs (no DB/firewall).",
    )
    parser.add_argument(
        "--urls",
        type=Path,
        default=_DEFAULT_URLS_FILE,
        help=f"File with one URL per line (default: {_DEFAULT_URLS_FILE})",
    )
    parser.add_argument(
        "--url",
        action="append",
        dest="cli_urls",
        metavar="URL",
        help="Additional URL(s) on the command line (repeatable)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=_DEFAULT_OUT_DIR,
        help=f"Output directory for JSON/CSV (default: {_DEFAULT_OUT_DIR})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    args = _parse_args(argv)
    urls = _load_urls(args.urls, args.cli_urls)
    return asyncio.run(_run_harness(urls, args.out))


if __name__ == "__main__":
    raise SystemExit(main())
