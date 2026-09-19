"""Per-host access-mode registry: how a shop is reachable, not how it renders.

Modes (dim_marketplace.access_mode):
  direct       - plain HTTP first, headless browser fallback (default)
  render       - headless browser first (JS storefront), plain HTTP fallback
  proxy        - residential proxy API only (datacenter IPs are blocked)
  proxy_render - residential proxy API with JS rendering

The registry is filled at the same points that register host_throttle
intervals (scrape / discovery load the marketplace row there) and is read by
scraper_pool._layer_order per URL. The paid proxy backend participates ONLY
in proxy modes — quota is never spent escalating a direct-mode shop.
"""

from __future__ import annotations

from urllib.parse import urlparse

MODE_DIRECT = "direct"
MODE_RENDER = "render"
MODE_PROXY = "proxy"
MODE_PROXY_RENDER = "proxy_render"

VALID_MODES = frozenset({MODE_DIRECT, MODE_RENDER, MODE_PROXY, MODE_PROXY_RENDER})

_host_modes: dict[str, str] = {}


def normalize_host(host: str) -> str:
    """Registry key for a host: lowercase, leading 'www.' dropped.

    dim_marketplace.base_url is stored apex ('https://tsbohemia.cz') while the
    enumerated listing URLs carry 'www.' — keyed on the raw netloc the mode
    never matched, so 11 proxy_render shops (~550k listings) silently fetched
    with a datacenter browser instead (2026-09-19 blocked% investigation).
    """
    host = host.strip().lower()
    return host[4:] if host.startswith("www.") else host


def _host_of(url: str) -> str:
    return normalize_host(urlparse(url).netloc or "")


def set_host_mode(base_url_or_host: object, mode: object) -> None:
    """Register a marketplace's access_mode for its host; garbage is ignored."""
    if not isinstance(base_url_or_host, str) or not isinstance(mode, str):
        return
    host = _host_of(base_url_or_host) or normalize_host(base_url_or_host)
    if not host:
        return
    normalized = mode.strip().lower()
    if normalized in VALID_MODES:
        _host_modes[host] = normalized


def mode_for(url: str | None) -> str:
    """Access mode for a URL's host; unregistered hosts default to direct."""
    if not url:
        return MODE_DIRECT
    return _host_modes.get(_host_of(url), MODE_DIRECT)


def wants_proxy_render(url: str | None) -> bool:
    return mode_for(url) == MODE_PROXY_RENDER
