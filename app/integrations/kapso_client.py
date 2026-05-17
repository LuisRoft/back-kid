import logging

import httpx

from app.config import settings

log = logging.getLogger(__name__)

_BASE = "https://app.kapso.ai/api/meta"


async def send_whatsapp_message(to: str, body: str) -> None:
    url = f"{_BASE}/{settings.KAPSO_PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            url,
            headers={"X-API-Key": settings.KAPSO_API_KEY},
            json=payload,
        )
        if not r.is_success:
            log.error("Kapso send failed %s: %s", r.status_code, r.text)
        r.raise_for_status()
