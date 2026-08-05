const BASE_URL = import.meta.env.VITE_BACKEND_API_URL ?? "http://localhost:8000";

export type CatalogEntry = {
  name: string;
  description: string;
  version: string;
  updated_at: string;
};

export type TemplateNode = {
  name: string;
  type: string;
};

export type TemplateDetail = {
  name: string;
  description: string;
  version: string;
  updated_at: string;
  nodes: TemplateNode[];
  tools: string[];
};

export type ExtractionWarning = {
  row_reference: string;
  field: string;
  issue: string;
  source?: string | null;
};

export type HoldingsSnapshot = {
  filename: string | null;
  uploaded_at: string | null;
  holdings_count: number;
  warnings: ExtractionWarning[];
};

export type ReconciliationDocType =
  | "ledger"
  | "custodian_statement"
  | "trade_blotter"
  | "corporate_actions";

export type ReconciliationDataOut = {
  doc_type: ReconciliationDocType;
  filename: string | null;
  uploaded_at: string | null;
  row_count: number;
  warnings: ExtractionWarning[];
};

export type DataSourceStatus = {
  key: string;
  label: string;
  description: string;
  required: boolean;
  kind: "holdings" | "reconciliation";
  accept: string[];
  filename: string | null;
  uploaded_at: string | null;
  count: number;
  warnings: ExtractionWarning[];
};

export type Decision = "approved" | "rejected";

export type PendingApproval = {
  agent_id: number;
  report: string;
  message: string;
};

export type ChatResponse = {
  thread_id: string;
  message: string;
  routed_to: string | null;
  pending_approval?: PendingApproval | null;
};

export type ChatDecisionRequest = {
  thread_id: string;
  decision: Decision;
  actor: string;
  comment: string | null;
};

export type HomeChatDecisionRequest = ChatDecisionRequest & {
  agent_id: number;
};

export type ToolInfo = {
  name: string;
  description: string;
};

export type LlmConfig = {
  temperature: number | null;
  max_tokens: number | null;
};

export type AgentInstance = {
  id: number;
  template_name: string;
  display_name: string;
  description: string;
  instructions: string | null;
  status: "draft" | "deployed";
  included_in_chat: boolean;
  extra_tools: string[];
  llm_config: LlmConfig;
  created_at: string;
  updated_at: string;
};

export type UpdateAgentInstanceRequest = {
  display_name?: string;
  description?: string;
  instructions?: string;
  included_in_chat?: boolean;
  llm_config?: LlmConfig;
  extra_tools?: string[];
};

export type AgentDocument = {
  id: number;
  instance_id: number;
  filename: string;
  chunk_count: number;
  created_at: string;
  effective_date: string | null;
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || `Request failed with status ${resp.status}`);
  }
  return resp.json() as Promise<T>;
}

async function requestFormData<T>(path: string, formData: FormData, method = "POST"): Promise<T> {
  // No Content-Type header here — the browser sets multipart/form-data with
  // the correct boundary itself; setting it manually breaks the upload.
  const resp = await fetch(`${BASE_URL}${path}`, { method, body: formData });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || `Request failed with status ${resp.status}`);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  getCatalog: () => request<CatalogEntry[]>("/catalog"),

  getTemplate: (templateName: string) =>
    request<TemplateDetail>(`/templates/${templateName}`),

  listTools: () => request<ToolInfo[]>("/tools"),

  chat: (message: string, threadId: string | null) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify({ message, thread_id: threadId }),
    }),

  submitChatDecision: (body: HomeChatDecisionRequest) =>
    request<ChatResponse>("/chat/decision", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listAgents: () => request<AgentInstance[]>("/agents"),

  getAgent: (agentId: number) => request<AgentInstance>(`/agents/${agentId}`),

  createAgent: (templateName: string, displayName: string, description: string) =>
    request<AgentInstance>("/agents", {
      method: "POST",
      body: JSON.stringify({
        template_name: templateName,
        display_name: displayName,
        description,
      }),
    }),

  updateAgent: (agentId: number, fields: UpdateAgentInstanceRequest) =>
    request<AgentInstance>(`/agents/${agentId}`, {
      method: "PATCH",
      body: JSON.stringify(fields),
    }),

  deployAgent: (agentId: number) =>
    request<AgentInstance>(`/agents/${agentId}/deploy`, { method: "POST" }),

  deleteAgent: (agentId: number) =>
    request<AgentInstance>(`/agents/${agentId}`, { method: "DELETE" }),

  listDocuments: (agentId: number) => request<AgentDocument[]>(`/agents/${agentId}/documents`),

  uploadDocument: (agentId: number, file: File, effectiveDate?: string) => {
    const formData = new FormData();
    formData.append("file", file);
    if (effectiveDate) formData.append("effective_date", effectiveDate);
    return requestFormData<AgentDocument>(`/agents/${agentId}/documents`, formData);
  },

  deleteDocument: (agentId: number, documentId: number) =>
    request<AgentDocument>(`/agents/${agentId}/documents/${documentId}`, {
      method: "DELETE",
    }),

  chatWithAgent: (agentId: number, message: string, threadId: string | null) =>
    request<ChatResponse>(`/agents/${agentId}/chat`, {
      method: "POST",
      body: JSON.stringify({ message, thread_id: threadId }),
    }),

  submitAgentChatDecision: (agentId: number, body: ChatDecisionRequest) =>
    request<ChatResponse>(`/agents/${agentId}/chat/decision`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getHoldings: (agentId: number) => request<HoldingsSnapshot>(`/agents/${agentId}/holdings`),

  uploadHoldings: (agentId: number, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return requestFormData<HoldingsSnapshot>(`/agents/${agentId}/holdings`, formData);
  },

  getReconciliationData: (agentId: number) =>
    request<ReconciliationDataOut[]>(`/agents/${agentId}/reconciliation-data`),

  uploadReconciliationData: (agentId: number, docType: ReconciliationDocType, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return requestFormData<ReconciliationDataOut>(
      `/agents/${agentId}/reconciliation-data/${docType}`,
      formData,
    );
  },

  getDataSources: (agentId: number) =>
    request<DataSourceStatus[]>(`/agents/${agentId}/data-sources`),
};
