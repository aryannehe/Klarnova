from typing import Any

from pydantic import BaseModel


class BanditContext(BaseModel):
    incident_category: str
    severity: str
    features: dict[str, Any]
    candidate_actions: list[str]
