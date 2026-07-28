from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class CatalogEntry(BaseModel):
    name: str
    description: str
    version: str
    updated_at: datetime


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


class ChatRequest(BaseModel):
    thread_id: str | None = None
    message: str


class ChatResponse(BaseModel):
    thread_id: str
    message: str
    routed_to: str | None = None
