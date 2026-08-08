from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentRunBase(BaseModel):
    incident_id: int
    agent_name: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)

class AgentRunCreate(AgentRunBase):
    pass

class AgentRun(AgentRunBase):
    id: int
    
    class Config:
        from_attributes = True
