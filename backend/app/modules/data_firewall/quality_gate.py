"""Rust-backed data-quality assessment (rust_core::quality).

Sits between extraction and the ecommerce door: scores every scraped record
0..100 with machine-readable flags. Rollout is staged via QUALITY_GATE_MODE:

* ``off``      — never assess;
* ``observe``  — assess + structured log only (default: collect score
  distribution on live traffic before any enforcement);
* ``enforce``  — additionally report records with critical flags as
  reject-worthy to the caller (the ingestion pipeline skips persistence).

The scoring itself lives in the Rust module (backend/rust_core, module
``imperecta_core``); when the extension is not built this gate is a no-op —
the classic door pipeline stays fully authoritative either way.
"""

from __future__ import annotations

import os
from typing import Any

import structlog

from app.common.ops_alerts import emit_ops_alert

try:  # optional compiled core
    import imperecta_core as _rust_core
except ImportError:  # pragma: no cover - depends on build environment
    _rust_core = None

slog = structlog.get_logger(__name__)

_VALID_MODES = {"off", "observe", "enforce"}
_LOW_SCORE_ALERT_THRESHOLD = 40


def quality_mode() -> str:
    mode = os.getenv("QUALITY_GATE_MODE", "observe").strip().lower()
    return mode if mode in _VALID_MODES else "observe"


def quality_available() -> bool:
    return _rust_core is not None


def assess_extracted(
    data: Any,
    *,
    url: str | None,
    allowed_currencies: list[str] | tuple[str, ...] | frozenset[str] | None,
    marketplace_id: Any = None,
) -> dict[str, Any] | None:
    """Score one ExtractedProduct-shaped object; None when off/unavailable.

    Fail-open by contract: an observer must never break the pipeline, so any
    scoring error is logged and swallowed.
    """
    if _rust_core is None or quality_mode() == "off":
        return None
    try:
        report = _assess(data, url=url, allowed_currencies=allowed_currencies)
    except Exception as exc:
        slog.warning("quality_assessment_failed", error=str(exc)[:300], url=url)
        return None
    _alert_on_report(report, url=url, marketplace_id=marketplace_id)
    return report


def _alert_on_report(
    report: dict[str, Any],
    *,
    url: str | None,
    marketplace_id: Any,
) -> None:
    """service_alerts (module=quality): critical flags + low-score records."""
    entity = str(marketplace_id) if marketplace_id is not None else (url or "")
    context = {
        "score": report["score"],
        "grade": report["grade"],
        "flags": report["flags"],
        "marketplace_id": str(marketplace_id) if marketplace_id is not None else None,
    }
    if report["critical"]:
        emit_ops_alert(
            module="quality",
            submodule="assessment",
            severity="warning",
            anomaly_type="quality_critical",
            message=(
                f"Quality critical flags={','.join(report['flags'][:4])} "
                f"score={report['score']} marketplace_id={context['marketplace_id']}"
            ),
            entity=entity,
            context=context,
        )
    elif report["score"] < _LOW_SCORE_ALERT_THRESHOLD:
        emit_ops_alert(
            module="quality",
            submodule="assessment",
            severity="info",
            anomaly_type="quality_low_score",
            message=(
                f"Quality low score={report['score']} grade={report['grade']} "
                f"marketplace_id={context['marketplace_id']}"
            ),
            entity=entity,
            context=context,
        )


def _assess(
    data: Any,
    *,
    url: str | None,
    allowed_currencies: list[str] | tuple[str, ...] | frozenset[str] | None,
) -> dict[str, Any]:
    category_path = getattr(data, "category_path", None)
    record: dict[str, Any] = {
        "title": getattr(data, "title", None),
        "price": (
            float(data.price) if getattr(data, "price", None) is not None else None
        ),
        "original_price": (
            float(data.original_price)
            if getattr(data, "original_price", None) is not None
            else None
        ),
        "currency": getattr(data, "currency", None),
        "currency_raw": getattr(data, "currency_raw", None),
        "image_url": getattr(data, "image_url", None),
        "url": url,
        "description": getattr(data, "description", None),
        "brand": getattr(data, "brand", None),
        "category_path": list(category_path) if category_path else None,
        "allowed_currencies": sorted(allowed_currencies) if allowed_currencies else [],
    }
    report = _rust_core.assess_quality(record)

    slog.info(
        "DATA_QUALITY",
        score=report["score"],
        grade=report["grade"],
        flags=report["flags"],
        critical=report["critical"],
        mode=quality_mode(),
        url=url,
    )
    return report


def should_reject(report: dict[str, Any] | None) -> bool:
    """True only in enforce mode AND when the report carries a critical flag."""
    return (
        report is not None
        and quality_mode() == "enforce"
        and bool(report.get("critical"))
    )
