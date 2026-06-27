"""Pure per-phase deadline allocation for discovery category path."""

from __future__ import annotations

import time

# When Phase 2 has category backlog, Phase 1 may consume at most this fraction of
# the remaining headroom budget; Phase 2 keeps the full headroom deadline.
PHASE1_BACKLOG_CAP_FRACTION = 0.30


def allocate(
    headroom_deadline: float | None,
    has_backlog: bool,
) -> tuple[float | None, float | None]:
    """Split headroom into Phase 1 and Phase 2 monotonic deadlines.

    Formula (headroom_deadline = H, now = time.monotonic()):
      remaining = max(0, H - now)
      has_backlog=True  -> phase1 = now + 0.30 * remaining, phase2 = H
      has_backlog=False -> phase1 = H, phase2 = H
      H is None         -> (None, None)
    """
    if headroom_deadline is None:
        return None, None
    now = time.monotonic()
    remaining_headroom = max(0.0, headroom_deadline - now)
    if has_backlog:
        phase1_deadline = now + remaining_headroom * PHASE1_BACKLOG_CAP_FRACTION
        phase2_deadline = headroom_deadline
    else:
        phase1_deadline = headroom_deadline
        phase2_deadline = headroom_deadline
    return phase1_deadline, phase2_deadline
