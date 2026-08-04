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


class ToolInfo(BaseModel):
    name: str
    description: str


class ExtractionWarningOut(BaseModel):
    row_reference: str
    field: str
    issue: str
    # Which uploaded document this warning came from — only set for
    # reconciliation's multi-document warnings, since holdings only ever has
    # one source document.
    source: str | None = None


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


class DataSourceStatusOut(BaseModel):
    key: str
    label: str
    description: str
    required: bool
    kind: Literal["holdings", "reconciliation"]
    accept: list[str]
    filename: str | None = None
    uploaded_at: datetime | None = None
    count: int = 0
    warnings: list[ExtractionWarningOut] = []


class ChatRequest(BaseModel):
    thread_id: str | None = None
    message: str


class PendingApprovalOut(BaseModel):
    report: str
    message: str


class ChatResponse(BaseModel):
    thread_id: str
    message: str
    routed_to: str | None = None
    # Set instead of a normal message when the agent's chat paused mid-turn
    # waiting on a human approve/reject decision (the chat-driven report
    # flow) — the frontend renders this as an inline approval card rather
    # than plain text.
    pending_approval: PendingApprovalOut | None = None


class ChatDecisionRequest(BaseModel):
    thread_id: str
    decision: Literal["approved", "rejected"]
    actor: str
    comment: str | None = None


class AgentInstance(BaseModel):
    id: int
    template_name: str
    display_name: str
    description: str
    instructions: str | None = None
    status: Literal["draft", "deployed"]
    included_in_chat: bool = False
    extra_tools: list[str] = []
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
    extra_tools: list[str] | None = None


class AgentDocument(BaseModel):
    id: int
    instance_id: int
    filename: str
    chunk_count: int
    created_at: datetime
