"""Discovery tuning constants — dependency-light (no orchestrator/persist imports)."""

# Must match bfs_walker.CATEGORY_PUBLISH_BATCH (re-export avoided to keep this module import-light).
CATEGORY_PUBLISH_BATCH = 60

# Days before category recon is re-run for a marketplace.
CATEGORY_RECON_STALE_DAYS = 7
# Days before sitemap harvest is re-run.
SITEMAP_STALE_DAYS = 3
# Persist batch size for _save_product_urls. Large sitemaps (e.g., 20k+ URLs)
# cannot be saved in a single transaction within DISCOVERY_PER_MARKETPLACE_BUDGET_SECONDS —
# the monolithic flush takes >14 minutes and gets cancelled by the circuit breaker,
# losing all work. Batched commits ensure progress survives cancel: each committed
# batch is durable, and the next run sees its URLs via existing_hashes lookup.
#
# 500 is a balance between round-trip overhead (smaller batches = more flushes)
# and lost-work-on-cancel (larger batches = bigger loss when cancel hits mid-batch).
SAVE_PRODUCT_URLS_BATCH_SIZE = 500
# Fraction of the per-marketplace discovery budget that
# _save_product_urls is allowed to consume before voluntarily
# exiting with a resumable offset. The remaining 15% is
# headroom for finalization (final commit of marketplace row,
# status updates, return path) so the caller never has to
# hard-cancel us mid-commit.
SAVE_BUDGET_HEADROOM_FRACTION = 0.85
# Min URLs found via sitemap to consider sitemap harvest successful.
SITEMAP_MIN_USEFUL_URLS = 10
# Sampling strategy for content-aware sitemap classification.
# If sitemap returns <= SITEMAP_FULL_CLASSIFY_LIMIT URLs, classify all of them.
# Otherwise classify only a random sample to decide whether to trust the sitemap.
SITEMAP_FULL_CLASSIFY_LIMIT = 100
# Size of random sample taken from large sitemaps for trust assessment.
SITEMAP_SAMPLE_SIZE = 50
# If less than this fraction of the sample classifies as 'product',
# reject the entire sitemap and fall back to category recon.
SITEMAP_REJECT_THRESHOLD = 0.20
# Max concurrent classification fetches (HTTP throttle).
SITEMAP_CLASSIFY_CONCURRENCY = 8

# ---------------------------------------------------------------------------
# Universal timeout policy: three-level defence against slow/broken marketplaces.
# ---------------------------------------------------------------------------
# These budgets bound how long discovery can spend per marketplace, ensuring
# one slow or unreachable site cannot stall the entire pipeline. Values are
# intentionally permissive to keep correctness as the priority — fast retries
# would risk losing slow-but-valid marketplaces. Tuning happens via these
# constants only; no per-marketplace overrides.

# Per sitemap-phase budget. If harvest_sitemap does not produce URLs
# within this window, the sitemap path is abandoned and discovery falls back
# to category-recon path for this marketplace.
SITEMAP_PHASE_BUDGET_SECONDS = 300  # 5 minutes

# Per-marketplace total discovery budget (sitemap + category recon together).
# If the full discover() call exceeds this, the marketplace is marked as
# timeout_skipped with 24-hour cooldown and the pipeline continues with the
# next marketplace.
DISCOVERY_PER_MARKETPLACE_BUDGET_SECONDS = 900  # 15 minutes

# Cooldown applied to sitemap_harvest when sitemap times out (asyncio.TimeoutError).
# Longer than SITEMAP_BAD_HARVEST_RETRY_HOURS because a timeout
# signals a persistent issue (very slow server, anti-bot, network partition) —
# retrying in an hour would just burn another budget cycle.
SITEMAP_TIMEOUT_COOLDOWN_HOURS = 24

# Cooldown after a bad (non-useful) sitemap harvest before retry.
SITEMAP_BAD_HARVEST_RETRY_HOURS = 1
# Consecutive non-useful sitemap harvests before sitemap_useful_false alert.
SITEMAP_USEFUL_FALSE_STREAK_THRESHOLD = 3

__all__ = [
    "CATEGORY_PUBLISH_BATCH",
    "CATEGORY_RECON_STALE_DAYS",
    "DISCOVERY_PER_MARKETPLACE_BUDGET_SECONDS",
    "SAVE_BUDGET_HEADROOM_FRACTION",
    "SAVE_PRODUCT_URLS_BATCH_SIZE",
    "SITEMAP_BAD_HARVEST_RETRY_HOURS",
    "SITEMAP_CLASSIFY_CONCURRENCY",
    "SITEMAP_FULL_CLASSIFY_LIMIT",
    "SITEMAP_MIN_USEFUL_URLS",
    "SITEMAP_PHASE_BUDGET_SECONDS",
    "SITEMAP_REJECT_THRESHOLD",
    "SITEMAP_SAMPLE_SIZE",
    "SITEMAP_STALE_DAYS",
    "SITEMAP_TIMEOUT_COOLDOWN_HOURS",
    "SITEMAP_USEFUL_FALSE_STREAK_THRESHOLD",
]
