from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PipelineRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_name: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None
