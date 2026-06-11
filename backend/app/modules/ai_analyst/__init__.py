"""AI analyst module - chat core (POST /ai/chat) + Claude model resolver.

Public surface:
    - api.router: POST /ai/chat (the only live AI route; gated by
      Feature.AI_ANALYST through a router-level dependency).
    - service.chat: persists AIChatSession/AIChatMessage history and calls
      Anthropic; history accrues for the future AI agent.
    - claude_client.resolve_claude_model: model id resolver (explicit | auto |
      auto:<family>) imported by `app.modules.core.api_admin` for the admin
      /claude-status endpoint.

AI1 removed the dead session-list/detail/delete routes, monitor.py, the orphan
digest helpers (DA1 leftovers), build_user_context, auto_categorize, and the
NotImplementedError stubs. Canonical ORM models (AIChatSession, AIChatMessage,
ApiLog) live in app.models, not here.
"""
