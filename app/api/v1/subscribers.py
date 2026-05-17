from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import SubscriberRepo
from app.dependencies import get_db
from app.integrations.twilio_client import send_sms
from app.models.subscriber import Subscriber

router = APIRouter(prefix="/subscribers", tags=["subscribers"])


class SubscriberIn(BaseModel):
    phone: str
    name: str | None = None


class SubscriberOut(BaseModel):
    phone: str
    name: str | None
    is_active: bool


@router.post("", response_model=SubscriberOut, status_code=201)
async def create_subscriber(
    payload: SubscriberIn,
    db: AsyncSession = Depends(get_db),
) -> Subscriber:
    repo = SubscriberRepo(db)
    return await repo.insert(Subscriber(phone=payload.phone, name=payload.name))


@router.get("", response_model=list[SubscriberOut])
async def list_subscribers(db: AsyncSession = Depends(get_db)) -> list[Subscriber]:
    return await SubscriberRepo(db).list_active()


@router.post("/test-sms")
async def test_sms(payload: SubscriberIn) -> dict:
    try:
        await send_sms(
            to=payload.phone,
            body="[NIMBUS TEST] SMS de prueba funcionando correctamente.",
        )
        return {"status": "sent", "to": payload.phone}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
