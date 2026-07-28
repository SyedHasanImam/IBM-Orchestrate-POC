from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class LlmAgentNodeConfig(BaseModel):
    name: str
    type: Literal["llm_agent"] = "llm_agent"
    model: str
    system_prompt: str
    tools: list[str] = Field(default_factory=list)
    message_template: str
    output_key: str


class ApprovalGateNodeConfig(BaseModel):
    name: str
    type: Literal["approval_gate"] = "approval_gate"
    report_key: str
    message: str


class FinalizeNodeConfig(BaseModel):
    name: str
    type: Literal["finalize"] = "finalize"
    report_key: str


NodeConfig = Annotated[
    Union[LlmAgentNodeConfig, ApprovalGateNodeConfig, FinalizeNodeConfig],
    Field(discriminator="type"),
]


class WorkflowConfig(BaseModel):
    """A fixed-edge pipeline: nodes execute in list order, no conditional
    routing. That's a deliberate scope limit, not an oversight — the
    workflows this factory builds are audit-critical "generate the official
    report" paths, where the step order must be provably fixed rather than
    LLM-decided."""

    name: str
    description: str
    version: str = "0.1.0"
    state_keys: list[str]
    nodes: list[NodeConfig]
