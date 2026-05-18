import logging

import httpx

from app.config import settings

log = logging.getLogger(__name__)

_API = "https://api.twilio.com/2010-04-01/Accounts"


async def send_sms(to: str, body: str) -> None:
    url = f"{_API}/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            url,
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            data={"From": settings.TWILIO_FROM, "To": to, "Body": body},
        )
        if not r.is_success:
            log.error("Twilio send failed %s: %s", r.status_code, r.text)
            r.raise_for_status()
