from typing import Literal

from pydantic import BaseModel


class RunReportResponse(BaseModel):
    thread_id: str
    report: str
    message: str


class DecisionRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    actor: str
    comment: str | None = None


class DecisionResponse(BaseModel):
    audit_log_id: int
    event_type: str
