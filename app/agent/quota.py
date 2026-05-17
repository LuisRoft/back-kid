"""Per-turn quota guard for expensive agent tools (currently web_search).

Tracks the count of tool calls per session within a sliding window. Stored in
process memory — sufficient for a single FastAPI worker. If we go multi-worker
later, swap for Redis.
"""
from __future__ import annotations

import contextvars
import time

# Set by the chat handler before invoking query(). The tool reads it.
_current_session: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "agent_session_id", default=None
)

# session_id -> list[timestamp]
_calls: dict[str, list[float]] = {}
WINDOW_SECONDS = 60 * 60  # 1h


def bind_session(session_id: str | None) -> contextvars.Token:
    return _current_session.set(session_id)


def unbind_session(token: contextvars.Token) -> None:
    _current_session.reset(token)


def current_session() -> str | None:
    return _current_session.get()


def check_and_increment(*, max_calls: int) -> tuple[bool, int]:
    """Increment counter for the current session if under quota.

    Returns (allowed, remaining_after_this_call).
    If no session is bound, always allows (used during tests / direct calls).
    """
    session = current_session()
    if session is None:
        return True, max_calls - 1

    now = time.monotonic()
    window = _calls.setdefault(session, [])
    # Drop old timestamps outside the window.
    cutoff = now - WINDOW_SECONDS
    while window and window[0] < cutoff:
        window.pop(0)

    if len(window) >= max_calls:
        return False, 0

    window.append(now)
    return True, max_calls - len(window)
