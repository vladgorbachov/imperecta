"""Grant imperecta_app INSERT on service_alerts (gate-failure carve-out).

Revision ID: 045_grant_app_insert_service_alerts
Revises: 044_widen_scrape_logs_status
Create Date: 2026-06-29

Enables the SERVICE-alert carve-out: write_service_alert_isolated can record
gate-failure alerts when the gate itself is down (same category as reject_data
INSERT). SELECT on service_alerts is already granted in 040. No RLS on
service_alerts — no policy needed.

Exclude this INSERT grant from the 9.6 DML revoke pass (like reject_data).
"""

from __future__ import annotations

from alembic import op

revision = "045_grant_app_insert_service_alerts"
down_revision = "044_widen_scrape_logs_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT INSERT ON service_alerts TO imperecta_app;")


def downgrade() -> None:
    op.execute("REVOKE INSERT ON service_alerts FROM imperecta_app;")
