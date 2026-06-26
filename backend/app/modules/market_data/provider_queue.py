"""Cross-provider Q-B gap-filling queue for market-data instrument fetches."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Generic, Protocol, Sequence, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class InstrumentProvider(Protocol[T]):
    """One provider asked only for still-missing instrument keys."""

    @property
    def provider_source(self) -> str:
        """Stable provider id carried on each result (e.g. openexchangerates, ecb)."""
        ...

    async def fetch_instruments(self, requested: frozenset[str]) -> dict[str, T]:
        """Return keyed results for a subset of ``requested``; omit absent keys."""
        ...


@dataclass(frozen=True)
class GapFillResult(Generic[T]):
    """Accumulated instruments and keys no provider supplied."""

    items: dict[str, tuple[T, str]]
    missing: frozenset[str]


async def gap_fill_fetch(
    providers: Sequence[InstrumentProvider[T]],
    requested: frozenset[str],
) -> GapFillResult[T]:
    """Ask providers in order; each provider receives only still-missing keys.

    First provider to supply an instrument wins; later providers fill gaps only.
    Intra-provider retries stay inside each provider; this layer is cross-provider.
    """
    accumulated: dict[str, tuple[T, str]] = {}
    missing: set[str] = set(requested)

    for provider in providers:
        if not missing:
            break
        try:
            batch = await provider.fetch_instruments(frozenset(missing))
        except Exception as exc:
            logger.warning(
                "provider_queue_fetch_failed source=%s err=%s",
                provider.provider_source,
                exc,
            )
            continue

        for key, item in batch.items():
            if key not in missing or key in accumulated:
                continue
            accumulated[key] = (item, provider.provider_source)
            missing.discard(key)

    return GapFillResult(items=accumulated, missing=frozenset(missing))


__all__ = ["GapFillResult", "InstrumentProvider", "gap_fill_fetch"]
