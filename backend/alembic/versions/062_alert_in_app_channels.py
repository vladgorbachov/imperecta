"""Alerts: in_app channel + multi-channel `channels` set (P15 §1).

Revision ID: 062_alert_in_app_channels
Revises: 061_product_match_columns
Create Date: 2026-09-18

The deployed create-alert dialog ships channel toggles with in_app as the
default, so the most common POST /alerts failed on two layers: the API enum
and the DB CHECK (channel IN ('email','telegram','push','webhook','all')).

1. ck_alerts_channel gains 'in_app' (legacy values kept — existing rows must
   keep passing the CHECK).
2. New `channels jsonb` — the full enabled set as a JSON array of channel
   names. jsonb, not text[]: the gate writer casts each signed value from its
   canonical string, and canonical_str() serializes a Python list as compact
   JSON, which casts cleanly to jsonb ('["email","in_app"]'::jsonb) but not
   to text[]. ck_alerts_channels enforces: NULL, or a non-empty array that is
   a subset of the known channel names (jsonb <@ containment).
3. Backfill: channels = to_jsonb(ARRAY[channel]) for existing rows (P15 §1.4;
   the table holds a handful of rows — plain in-transaction UPDATE).

Semantic validation (non-empty, no duplicates, webhook_url pairing) lives in
the ALERT door; the CHECK is the last-resort shape guard.
"""

from __future__ import annotations

from alembic import op

revision = "062_alert_in_app_channels"
down_revision = "061_product_match_columns"
branch_labels = None
depends_on = None

_CHANNEL_VALUES = "'email','telegram','push','webhook','all','in_app'"
_CHANNELS_JSONB_SET = '["email","telegram","push","webhook","all","in_app"]'


def upgrade() -> None:
    op.execute("ALTER TABLE alerts DROP CONSTRAINT IF EXISTS ck_alerts_channel")
    op.execute(
        "ALTER TABLE alerts ADD CONSTRAINT ck_alerts_channel "
        f"CHECK (channel IN ({_CHANNEL_VALUES}))"
    )
    op.execute("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS channels jsonb")
    op.execute("ALTER TABLE alerts DROP CONSTRAINT IF EXISTS ck_alerts_channels")
    op.execute(
        "ALTER TABLE alerts ADD CONSTRAINT ck_alerts_channels CHECK ("
        "channels IS NULL OR ("
        "jsonb_typeof(channels) = 'array' "
        "AND jsonb_array_length(channels) >= 1 "
        f"AND channels <@ '{_CHANNELS_JSONB_SET}'::jsonb"
        "))"
    )
    op.execute(
        "UPDATE alerts SET channels = to_jsonb(ARRAY[channel]) "
        "WHERE channels IS NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE alerts DROP CONSTRAINT IF EXISTS ck_alerts_channels")
    op.execute("ALTER TABLE alerts DROP COLUMN IF EXISTS channels")
    # Rows created with channel='in_app' would violate the narrow CHECK.
    op.execute("UPDATE alerts SET channel = 'email' WHERE channel = 'in_app'")
    op.execute("ALTER TABLE alerts DROP CONSTRAINT IF EXISTS ck_alerts_channel")
    op.execute(
        "ALTER TABLE alerts ADD CONSTRAINT ck_alerts_channel "
        "CHECK (channel IN ('email','telegram','push','webhook','all'))"
    )
