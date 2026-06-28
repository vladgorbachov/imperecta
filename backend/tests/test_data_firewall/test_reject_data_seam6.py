"""DB-free tests for reject_data seam 6 (sanctioned diagnostic carve-out #34-35)."""

from __future__ import annotations

from pathlib import Path

from app.modules.data_firewall.reject_store import SANCTIONED_REJECT_DATA_INSERT_FUNCTIONS
from app.modules.persist.writer import SUPPORTED_WRITE_OPERATIONS

BACKEND_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = BACKEND_ROOT / "app"


def _iter_python_sources() -> list[Path]:
    return sorted(APP_ROOT.rglob("*.py"))


def test_reject_data_insert_only_via_reject_store() -> None:
    reject_store = APP_ROOT / "modules/data_firewall/reject_store.py"
    model_path = APP_ROOT / "models/reject_data.py"
    offenders: list[str] = []
    for path in _iter_python_sources():
        if path in (reject_store, model_path):
            continue
        source = path.read_text(encoding="utf-8")
        if "RejectData(" in source:
            offenders.append(str(path.relative_to(BACKEND_ROOT)))
    assert offenders == []


def test_reject_store_is_unsigned_carve_out_not_gate_routed() -> None:
    source = (APP_ROOT / "modules/data_firewall/reject_store.py").read_text(
        encoding="utf-8",
    )
    assert "evaluate_market(" not in source
    assert "evaluate_ecommerce(" not in source
    assert "evaluate_logs(" not in source
    assert "write_sync(" not in source
    assert "authorize_retention_delete(" not in source
    assert "sign(" not in source
    assert "SANCTIONED_REJECT_DATA_INSERT_FUNCTIONS" in source
    assert "write_reject_data" in SANCTIONED_REJECT_DATA_INSERT_FUNCTIONS
    assert "write_reject_data_isolated" in SANCTIONED_REJECT_DATA_INSERT_FUNCTIONS


def test_reject_data_gated_delete_carve_out_insert_asymmetry() -> None:
    ops = SUPPORTED_WRITE_OPERATIONS["reject_data"]
    assert ops == frozenset({"retention_delete"})
    assert "insert" not in ops


def test_architecture_principles_documents_reject_data_carve_out() -> None:
    source = (BACKEND_ROOT.parent / "ARCHITECTURE_PRINCIPLES.md").read_text(
        encoding="utf-8",
    )
    assert "reject_data INSERT — sanctioned diagnostic carve-out" in source
    assert "write_reject_data" in source
    assert "write_reject_data_isolated" in source
    assert "CASCADE" in source
