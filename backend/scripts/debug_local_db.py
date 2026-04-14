#!/usr/bin/env python3
"""
Local DB diagnostics: Alembic revision + SQL snapshots + optional upgrade.

Run from repo root or backend/ with DATABASE_URL set (Windows / Linux).

Examples:
  cd backend && DATABASE_URL=postgresql://... python scripts/debug_local_db.py
  python backend/scripts/debug_local_db.py --upgrade
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPORT_NAME = "debug_local_db_report.md"


def _sync_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("ERROR: DATABASE_URL is not set", file=sys.stderr)
        sys.exit(2)
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


def _run_alembic(args: list[str]) -> tuple[int, str, str]:
    env = {**os.environ, "DATABASE_URL": os.environ.get("DATABASE_URL", "")}
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(BACKEND_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    return proc.returncode, (proc.stdout or ""), (proc.stderr or "")


def _write_report(path: Path, sections: list[tuple[str, str]]) -> None:
    lines = ["# Local DB diagnostics report", ""]
    for title, body in sections:
        lines.append(f"## {title}")
        lines.append("")
        lines.append(body.rstrip() or "(empty)")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug local Postgres + Alembic state")
    parser.add_argument(
        "--upgrade",
        action="store_true",
        help="Run `alembic upgrade head` before diagnostics",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(__file__).resolve().parent / REPORT_NAME,
        help=f"Markdown output path (default: scripts/{REPORT_NAME})",
    )
    args = parser.parse_args()

    _sync_database_url()

    sections: list[tuple[str, str]] = []

    code_cur, out_cur, err_cur = _run_alembic(["current"])
    current_block = f"exit={code_cur}\nSTDOUT:\n{out_cur}\nSTDERR:\n{err_cur}"
    sections.append(("alembic current", current_block))
    print(current_block)

    if args.upgrade:
        code_up, out_up, err_up = _run_alembic(["upgrade", "head"])
        upgrade_block = f"exit={code_up}\nSTDOUT:\n{out_up}\nSTDERR:\n{err_up}"
        sections.append(("alembic upgrade head", upgrade_block))
        print(upgrade_block)
        if code_up != 0:
            print("WARNING: upgrade head failed; continuing with diagnostics", file=sys.stderr)

    # Import after env is validated so SQLAlchemy can use DATABASE_URL from app settings
    sys.path.insert(0, str(BACKEND_ROOT))
    os.chdir(BACKEND_ROOT)
    import json

    from app.database import sync_engine
    from app.modules.scraper.db_diagnostics import collect_db_diagnostics

    diag = collect_db_diagnostics(sync_engine)

    diag_json = json.dumps(diag, indent=2, ensure_ascii=False)
    sections.append(("diagnostic payload (JSON)", f"```json\n{diag_json}\n```"))
    print(diag_json)

    _write_report(args.report, sections)
    print(f"\nReport written to: {args.report.resolve()}")


if __name__ == "__main__":
    main()
