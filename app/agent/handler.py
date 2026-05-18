from __future__ import annotations

import json
import logging

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent import quota
from app.agent.prompts import build_system_prompt
from app.agent.tools import hermes_server
from app.auth.clerk import CurrentUser, get_optional_user
from app.config import settings

router = APIRouter(prefix="/agent", tags=["agent"])
log = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


async def _stream(message: str, session_id: str | None, user: CurrentUser | None):
    system_prompt = build_system_prompt(user)
    env = {}
    if settings.ANTHROPIC_API_KEY:
        env["ANTHROPIC_API_KEY"] = settings.ANTHROPIC_API_KEY

    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        mcp_servers={"hermes": hermes_server},
        allowed_tools=["mcp__hermes__*"],
        tools=[],
        resume=session_id,
        max_turns=10,
        env=env,
    )

    session_key = session_id or (user.clerk_user_id if user else "anonymous")
    quota_token = quota.bind_session(session_key)
    try:
        try:
            async for msg in query(prompt=message, options=options):
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock) and block.text:
                            yield f"data: {json.dumps({'type': 'text', 'text': block.text})}\n\n"

                elif isinstance(msg, ResultMessage):
                    yield (
                        f"data: {json.dumps({'type': 'done', 'session_id': msg.session_id, 'is_error': msg.is_error})}\n\n"
                    )

            yield "data: [DONE]\n\n"
        except Exception as exc:  # noqa: BLE001
            log.exception("Hermes agent stream failed")
            yield f"data: {json.dumps({'type': 'text', 'text': 'Hermes no pudo completar la respuesta en este momento. Intenta de nuevo en unos segundos.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'is_error': True, 'error': str(exc)})}\n\n"
            yield "data: [DONE]\n\n"
    finally:
        quota.unbind_session(quota_token)


async def get_agent_response(message: str, session_id: str | None = None) -> str:
    """Returns the full agent response as a plain string (no streaming).
    Used by the WhatsApp webhook to get a reply before sending it back.
    No authenticated user — prompt built with None (anonymous citizen profile).
    """
    options = ClaudeAgentOptions(
        system_prompt=build_system_prompt(None),
        mcp_servers={"hermes": hermes_server},
        allowed_tools=["mcp__hermes__*"],
        tools=[],
        resume=session_id,
        max_turns=10,
    )
    parts: list[str] = []
    async for msg in query(prompt=message, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock) and block.text:
                    parts.append(block.text)
    return "".join(parts)


@router.post("/chat")
async def chat(
    request: ChatRequest,
    user: CurrentUser | None = Depends(get_optional_user),
) -> StreamingResponse:
    return StreamingResponse(
        _stream(request.message, request.session_id, user),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
