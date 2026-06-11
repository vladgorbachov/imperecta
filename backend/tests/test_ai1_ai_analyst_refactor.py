"""
AI1 ai_analyst refactor invariants (framework-light: no DB / no HTTP).

Verifies:
1. Dead surface gone: monitor.py uninstalled; the three session routes
   (/api/ai/sessions, /api/ai/sessions/{id} GET+DELETE) are not registered;
   only POST /api/ai/chat remains under /api/ai/.
2. Orphan service helpers removed (build_user_context, auto_categorize,
   get_price_recommendation, get_products_at_risk); chat() kept.
3. Orphan claude_client helpers removed (generate_digest, _fallback_digest,
   _parse_json_response); resolve_claude_model kept AND still imported by
   app.modules.core.api_admin (admin /claude-status invariant).
4. Orphan schemas (SessionListItem, SessionDetailResponse, MessageItem)
   removed; ChatRequest + ChatResponse survive.
5. Rule-6 named constants present (CHAT_HISTORY_DEPTH, CHAT_MAX_TOKENS,
   SESSION_TITLE_MAX_LEN, ANTHROPIC_HTTP_TIMEOUT_SECONDS); no bare
   20/2000/100/15.0 literals in the chat path.
6. Feature gate is a single router-level dependency; `has_feature` appears
   exactly once in the module (in the dependency).
7. No hardcoded-Russian digest prompt anywhere under ai_analyst.
8. Stray artifacts (init.py, models.py) gone; __init__.py is the only
   top-level non-source file.
9. chat() persists AIChatSession + AIChatMessage + ApiLog (A-keep semantics).
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest
from fastapi.routing import APIRoute

from app.main import app
from app.modules.ai_analyst import api as ai_api
from app.modules.ai_analyst import claude_client, schemas, service

AI_ANALYST_DIR = Path(__file__).resolve().parents[1] / "app" / "modules" / "ai_analyst"


# 1. dead surface -------------------------------------------------------------

def test_monitor_module_gone() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.modules.ai_analyst.monitor")


def test_only_chat_route_under_ai() -> None:
    pairs: set[tuple[str, str]] = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/api/ai/"):
            continue
        if isinstance(route, APIRoute):
            for method in sorted(route.methods - {"HEAD"}):
                pairs.add((method, path))

    assert pairs == {("POST", "/api/ai/chat")}, (
        f"AI1 should leave only POST /api/ai/chat under /api/ai/; found {pairs}"
    )


# 2. service helpers ----------------------------------------------------------

@pytest.mark.parametrize(
    "name",
    ["build_user_context", "auto_categorize", "get_price_recommendation", "get_products_at_risk"],
)
def test_orphan_service_helpers_removed(name: str) -> None:
    assert not hasattr(service, name), (
        f"ai_analyst.service.{name} should be deleted by AI1 (dead surface)."
    )


def test_chat_kept_and_async() -> None:
    import inspect

    assert hasattr(service, "chat"), "AI1 must keep service.chat()"
    assert inspect.iscoroutinefunction(service.chat)


# 3. claude_client ------------------------------------------------------------

@pytest.mark.parametrize(
    "name",
    ["generate_digest", "_fallback_digest", "_parse_json_response"],
)
def test_orphan_claude_helpers_removed(name: str) -> None:
    assert not hasattr(claude_client, name), (
        f"claude_client.{name} should be deleted by AI1 (DA1-orphan digest path)."
    )


def test_resolve_claude_model_intact() -> None:
    assert hasattr(claude_client, "resolve_claude_model")
    import inspect

    assert inspect.iscoroutinefunction(claude_client.resolve_claude_model)


def test_admin_still_imports_resolve_claude_model() -> None:
    """admin /claude-status invariant: api_admin.resolve_claude_model is the
    same object as claude_client.resolve_claude_model."""
    from app.modules.core import api_admin

    assert api_admin.resolve_claude_model is claude_client.resolve_claude_model


# 4. schemas ------------------------------------------------------------------

@pytest.mark.parametrize("name", ["SessionListItem", "SessionDetailResponse", "MessageItem"])
def test_orphan_session_schemas_removed(name: str) -> None:
    assert not hasattr(schemas, name), (
        f"schemas.{name} fed the deleted /ai/sessions routes and must be removed."
    )


def test_chat_schemas_kept() -> None:
    assert hasattr(schemas, "ChatRequest")
    assert hasattr(schemas, "ChatResponse")
    assert {"tokens_used", "duration_ms", "session_id", "response"} <= set(
        schemas.ChatResponse.model_fields.keys()
    )


# 5. Rule-6 named constants ---------------------------------------------------

def test_named_constants_present() -> None:
    assert service.CHAT_HISTORY_DEPTH == 20
    assert service.CHAT_MAX_TOKENS == 2000
    assert service.SESSION_TITLE_MAX_LEN == 100
    assert claude_client.ANTHROPIC_HTTP_TIMEOUT_SECONDS == 15.0


def test_no_bare_magic_numbers_in_chat_path() -> None:
    service_text = (AI_ANALYST_DIR / "service.py").read_text(encoding="utf-8")
    chat_section = service_text.split("async def chat(", 1)[1]

    forbidden = ["max_tokens=2000", "max_tokens=20", ".limit(20)", "message[:100]"]
    offenders = [literal for literal in forbidden if literal in chat_section]
    assert not offenders, f"Found bare magic literals in chat(): {offenders}"

    claude_text = (AI_ANALYST_DIR / "claude_client.py").read_text(encoding="utf-8")
    body_after_constants = claude_text.split("ANTHROPIC_HTTP_TIMEOUT_SECONDS", 2)[2]
    assert "timeout=15.0" not in body_after_constants, (
        "httpx.AsyncClient timeout must use the named constant."
    )


# 6. DRY feature gate ---------------------------------------------------------

def test_router_level_feature_dependency() -> None:
    deps = [d.dependency for d in (ai_api.router.dependencies or [])]
    assert ai_api.require_ai_analyst_feature in deps, (
        "AI1 must apply require_ai_analyst_feature at the router level."
    )


def test_has_feature_called_once() -> None:
    """has_feature must appear exactly once across ai_analyst (in the dep)."""
    hits = 0
    for path in AI_ANALYST_DIR.rglob("*.py"):
        hits += len(re.findall(r"\bhas_feature\(", path.read_text(encoding="utf-8")))
    assert hits == 1, (
        f"Expected 1 has_feature() call (router dependency); found {hits}"
    )


# 7. universality -------------------------------------------------------------

def test_no_hardcoded_russian_digest_prompt() -> None:
    pattern = re.compile(r"Пиши на русском|Дайджест|аналитик конкурентной")
    for path in AI_ANALYST_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not pattern.search(text), (
            f"Hardcoded-Russian digest prompt leaked into {path.name}"
        )


# 8. module artifacts ---------------------------------------------------------

def test_module_artifacts_clean() -> None:
    assert not (AI_ANALYST_DIR / "init.py").exists(), "stray init.py must be deleted"
    assert not (AI_ANALYST_DIR / "models.py").exists(), "placeholder models.py must be deleted"
    assert (AI_ANALYST_DIR / "__init__.py").exists()


# 9. chat() persistence (A-keep) ----------------------------------------------

def test_chat_persists_session_message_and_apilog() -> None:
    """A-keep semantics: chat() writes AIChatSession + AIChatMessage + ApiLog."""
    src = (AI_ANALYST_DIR / "service.py").read_text(encoding="utf-8")
    chat_section = src.split("async def chat(", 1)[1]
    assert "AIChatSession(" in chat_section, "chat() must persist AIChatSession"
    assert "AIChatMessage(" in chat_section, "chat() must persist AIChatMessage"
    assert "ApiLog(" in chat_section, "chat() must log Anthropic call via ApiLog"


def test_build_user_context_call_removed_from_chat() -> None:
    src = (AI_ANALYST_DIR / "service.py").read_text(encoding="utf-8")
    assert "build_user_context" not in src, (
        "AI1 must remove build_user_context entirely (definition + call)."
    )
