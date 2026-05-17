from __future__ import annotations

import json

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent.tools import hermes_server

router = APIRouter(prefix="/agent", tags=["agent"])

_SYSTEM_PROMPT = """You are Hermes, the AI assistant embedded in back-kid — Ecuador's critical infrastructure early warning system for El Niño events.

The system monitors precipitation forecasts (Open-Meteo) and NASA landslide hazard assessments (LHASA) to predict road corridor closures 24–72 hours in advance. It serves three actor types: government officials, logistics coordinators, and public health teams.

## Tools available
- get_active_alerts — all alerts where closure probability > 65% threshold, right now
- get_corridor_risks — corridors at risk for a given horizon (24h / 48h / 72h); also returns corridor_id for rerouting queries
- get_rerouting_plan — alternative route for a specific corridor (requires corridor_id UUID from the previous tools)
- get_health_risk — municipality epidemiological profiles + corridors currently at alert level

## How to respond
- Always call a tool before answering — never invent probabilities, corridor names, or route data
- If a tool returns an error, explain what failed and suggest what the user can try next
- Be concise and actionable — decision-makers need fast answers, not essays
- When reporting risk, always specify: corridor name, probability %, and horizon
- Respond in the same language as the user (Spanish or English)

## Ecuador context
Main corridors: E35 Quito–Guayaquil, E25 Babahoyo–Guayaquil, E20 Quito–Santo Domingo
Risk threshold: ≥65% probability triggers an alert
Horizons: 24h = immediate, 48h = tomorrow, 72h = day after tomorrow"""


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


async def _stream(message: str, session_id: str | None):
    options = ClaudeAgentOptions(
        system_prompt=_SYSTEM_PROMPT,
        mcp_servers={"hermes": hermes_server},
        allowed_tools=["mcp__hermes__*"],
        tools=[],           # disable built-in Read / Write / Bash
        resume=session_id,
        max_turns=10,
    )

    async for msg in query(prompt=message, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock) and block.text:
                    yield f"data: {json.dumps({'type': 'text', 'text': block.text})}\n\n"

        elif isinstance(msg, ResultMessage):
            yield f"data: {json.dumps({'type': 'done', 'session_id': msg.session_id, 'is_error': msg.is_error})}\n\n"

    yield "data: [DONE]\n\n"


@router.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        _stream(request.message, request.session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
