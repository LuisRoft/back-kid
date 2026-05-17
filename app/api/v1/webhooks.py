import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.agent.handler import get_agent_response
from app.integrations.kapso_client import send_whatsapp_message

log = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# In-memory session store: phone number → session_id
# Keeps conversation context per user across messages
_sessions: dict[str, str | None] = {}


@router.get("/whatsapp", response_class=PlainTextResponse)
async def whatsapp_verify(request: Request) -> str:
    """Webhook verification handshake required by Meta/Kapso on setup."""
    params = request.query_params
    if params.get("hub.mode") == "subscribe":
        return params.get("hub.challenge", "")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request) -> dict:
    """Receives incoming WhatsApp messages from Kapso, queries Hermes IA, replies."""
    body = await request.json()

    event_type = body.get("type")

    # Kapso sends delivery/read receipts back to the webhook (outbound status updates).
    # These are not user messages — acknowledge and skip.
    if event_type != "whatsapp.message.received":
        return {"status": "ignored"}

    try:
        items = body.get("data") or []
        if not items:
            return {"status": "no_message"}
        msg = items[0].get("message", {})
        if msg.get("type") != "text":
            return {"status": "ignored_non_text"}
        sender = msg["from"]
        text = msg["text"]["body"]
    except (KeyError, IndexError) as e:
        log.warning("Unexpected Kapso payload: %s — %s", e, body)
        return {"status": "unrecognized_payload"}

    log.info("WhatsApp message from %s: %s", sender, text)

    # Reuse existing session for this sender so conversation has memory
    session_id = _sessions.get(sender)
    reply = await get_agent_response(text, session_id)

    # Persist new session_id returned by the agent for next turn
    # (get_agent_response doesn't return it yet — extend later if needed)
    _sessions.setdefault(sender, None)

    try:
        await send_whatsapp_message(to=sender, body=reply)
    except Exception:
        log.exception("Failed to send WhatsApp reply to %s", sender)
        return {"status": "send_failed"}
    return {"status": "ok"}
