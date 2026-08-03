from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class CatalogEntry(BaseModel):
    name: str
    description: str
    version: str
    updated_at: datetime


class TemplateNodeSummary(BaseModel):
    name: str
    type: str


class TemplateDetail(BaseModel):
    name: str
    description: str
    version: str
    updated_at: datetime
    nodes: list[TemplateNodeSummary]
    tools: list[str]


class ExtractionWarningOut(BaseModel):
    row_reference: str
    field: str
    issue: str
    # Which uploaded document this warning came from — only set for
    # reconciliation's multi-document warnings, since holdings only ever has
    # one source document.
    source: str | None = None


class RunReportResponse(BaseModel):
    thread_id: str
    workflow_name: str
    report: str
    message: str
    extraction_warnings: list[ExtractionWarningOut] = []


class HoldingsSnapshot(BaseModel):
    filename: str | None = None
    uploaded_at: datetime | None = None
    holdings_count: int = 0
    warnings: list[ExtractionWarningOut] = []


class ReconciliationDataOut(BaseModel):
    doc_type: str
    filename: str | None = None
    uploaded_at: datetime | None = None
    row_count: int = 0
    warnings: list[ExtractionWarningOut] = []


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


class AgentInstance(BaseModel):
    id: int
    template_name: str
    display_name: str
    description: str
    instructions: str | None = None
    status: Literal["draft", "deployed"]
    included_in_chat: bool = False
    created_at: datetime
    updated_at: datetime


class CreateAgentInstanceRequest(BaseModel):
    template_name: str
    display_name: str
    description: str = ""


class UpdateAgentInstanceRequest(BaseModel):
    display_name: str | None = None
    description: str | None = None
    instructions: str | None = None
    included_in_chat: bool | None = None


class AgentDocument(BaseModel):
    id: int
    instance_id: int
    filename: str
    chunk_count: int
    created_at: datetime
