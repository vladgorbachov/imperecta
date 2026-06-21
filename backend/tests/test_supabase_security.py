"""Tests for Supabase security hardening helpers."""

from __future__ import annotations

from app.modules.core import supabase_security as sec


def test_harden_table_statements_cover_rls_policy_and_revoke() -> None:
    statements = sec.harden_table_statements("public.fact_price_202701")
    joined = "\n".join(statements)
    assert "ENABLE ROW LEVEL SECURITY" in joined
    assert "rls_deny_client_roles" in joined
    assert "USING (false)" in joined
    assert "REVOKE ALL ON public.fact_price_202701 FROM anon, authenticated" in joined
    assert "REVOKE SELECT ON public.fact_price_202701 FROM anon, authenticated" in joined


def test_schema_revoke_statements_target_client_roles() -> None:
    joined = "\n".join(sec.SCHEMA_REVOKE_STATEMENTS)
    assert "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated" in joined
    assert "ALTER DEFAULT PRIVILEGES" in joined


def test_harden_materialized_view_statements() -> None:
    statements = sec.harden_materialized_view_statements("mv_daily_price_summary")
    assert len(statements) == 2
    assert all("mv_daily_price_summary" in stmt for stmt in statements)
