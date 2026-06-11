"""Alerts module - shared notification delivery infrastructure.

The previous v2-migration stubs (api/service/schemas/tasks/notifications) were
deleted in DA1. The module now exposes ONLY the `notifications` submodule:
channel strategies (Telegram, email, ...) that deliver caller-composed
messages. Business alert routes / triggers (price drop, out of stock, etc.)
are not implemented here yet - they will be a future consumer of this
delivery infrastructure.
"""
