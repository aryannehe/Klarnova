
from pydantic import BaseModel, Field


class DiagnosisResult(BaseModel):
    root_cause: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    relevant_runbooks: list[str] = Field(default_factory=list)
