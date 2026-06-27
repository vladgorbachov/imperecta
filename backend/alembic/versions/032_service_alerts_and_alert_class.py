"""Create service_alerts and retro-sign alerts/alert_events with alert_class.

Revision ID: 032_service_alerts_and_alert_class
Revises: 031_listing_last_price_changed_idx
Create Date: 2026-06-17
"""

from alembic import op

from app.modules.persist.maintenance_audit import record_maintenance_audit

revision = "032_service_alerts_and_alert_class"
down_revision = "031_listing_last_price_changed_idx"
branch_labels = None
depends_on = None


def _audit_ddl(target: str, detail: str) -> None:
    """Record DDL through the LOGS door (api_logs maintenance audit mark)."""
    record_maintenance_audit(
        op="ALTER",
        target=target,
        status="success",
        detail=detail,
    )


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE service_alerts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            alert_class VARCHAR(20) NOT NULL DEFAULT 'service',
            module VARCHAR(64) NOT NULL,
            submodule VARCHAR(64) NOT NULL,
            severity VARCHAR(10) NOT NULL,
            anomaly_type VARCHAR(64) NOT NULL,
            message TEXT NOT NULL,
            context JSONB,
            triggered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            resolved_at TIMESTAMPTZ,
            CONSTRAINT ck_service_alerts_severity
                CHECK (severity IN ('info','warning','error','critical')),
            CONSTRAINT ck_service_alerts_alert_class
                CHECK (alert_class = 'service')
        )
        """
    )
    _audit_ddl("service_alerts", "CREATE TABLE service_alerts")

    op.execute(
        """
        CREATE INDEX idx_service_alerts_module_submodule_triggered
        ON service_alerts (module, submodule, triggered_at)
        """
    )
    _audit_ddl(
        "service_alerts.idx_service_alerts_module_submodule_triggered",
        "CREATE INDEX idx_service_alerts_module_submodule_triggered",
    )

    op.execute(
        """
        ALTER TABLE alerts
        ADD COLUMN IF NOT EXISTS alert_class VARCHAR(20) NOT NULL DEFAULT 'analytic'
        """
    )
    _audit_ddl("alerts.alert_class", "ADD COLUMN alert_class DEFAULT analytic")

    op.execute(
        """
        ALTER TABLE alert_events
        ADD COLUMN IF NOT EXISTS alert_class VARCHAR(20) NOT NULL DEFAULT 'analytic'
        """
    )
    _audit_ddl(
        "alert_events.alert_class",
        "ADD COLUMN alert_class DEFAULT analytic",
    )


def downgrade() -> None:
    op.execute("ALTER TABLE alert_events DROP COLUMN IF EXISTS alert_class")
    _audit_ddl("alert_events.alert_class", "DROP COLUMN alert_class")
    op.execute("ALTER TABLE alerts DROP COLUMN IF EXISTS alert_class")
    _audit_ddl("alerts.alert_class", "DROP COLUMN alert_class")
    op.execute("DROP INDEX IF EXISTS idx_service_alerts_module_submodule_triggered")
    _audit_ddl(
        "service_alerts.idx_service_alerts_module_submodule_triggered",
        "DROP INDEX idx_service_alerts_module_submodule_triggered",
    )
    op.execute("DROP TABLE IF EXISTS service_alerts")
    _audit_ddl("service_alerts", "DROP TABLE service_alerts")
