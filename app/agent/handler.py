from __future__ import annotations

import json

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent import quota
from app.agent.prompts import build_system_prompt
from app.agent.tools import hermes_server
from app.auth.clerk import CurrentUser, get_current_user

router = APIRouter(prefix="/agent", tags=["agent"])


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


async def _stream(message: str, session_id: str | None, user: CurrentUser):
    system_prompt = build_system_prompt(user)
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        mcp_servers={"hermes": hermes_server},
        allowed_tools=["mcp__hermes__*"],
        tools=[],
        resume=session_id,
        max_turns=10,
    )

    quota_token = quota.bind_session(session_id or user.clerk_user_id)
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
    finally:
        quota.unbind_session(quota_token)


@router.post("/chat")
async def chat(
    request: ChatRequest,
    user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    return StreamingResponse(
        _stream(request.message, request.session_id, user),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
