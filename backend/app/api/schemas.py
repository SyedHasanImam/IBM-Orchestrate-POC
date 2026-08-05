from datetime import date, datetime
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
    agent_id: int
    report: str
    message: str


class ChatResponse(BaseModel):
    thread_id: str
    message: str
    routed_to: str | None = None
    # Set whenever the agent(s) in this chat have a report waiting on a
    # human approve/reject decision — read directly off the report
    # pipeline's own state (see report_tool.get_pending_report), not tied to
    # this chat's own conversation state, so it surfaces the same way
    # whether asked from an agent's own chat or the homepage's multi-agent
    # one. The frontend renders this as an inline approval card rather than
    # plain text.
    pending_approval: PendingApprovalOut | None = None


class ChatDecisionRequest(BaseModel):
    thread_id: str
    decision: Literal["approved", "rejected"]
    actor: str
    comment: str | None = None


class HomeChatDecisionRequest(BaseModel):
    agent_id: int
    thread_id: str
    decision: Literal["approved", "rejected"]
    actor: str
    comment: str | None = None


class LlmConfig(BaseModel):
    """Optional per-agent model overrides (the Behavior tab's "Model
    settings") — real watsonx Orchestrate concept, left empty by default
    so an agent just uses its template's plain model with no override."""

    temperature: float | None = None
    max_tokens: int | None = None


class AgentInstance(BaseModel):
    id: int
    template_name: str
    display_name: str
    description: str
    instructions: str | None = None
    status: Literal["draft", "deployed"]
    included_in_chat: bool = False
    extra_tools: list[str] = []
    llm_config: LlmConfig = LlmConfig()
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
    llm_config: LlmConfig | None = None


class AgentDocument(BaseModel):
    id: int
    instance_id: int
    filename: str
    chunk_count: int
    created_at: datetime
    effective_date: date | None = None
