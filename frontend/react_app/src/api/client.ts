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

export type RunReportResponse = {
  thread_id: string;
  workflow_name: string;
  report: string;
  message: string;
  extraction_warnings: ExtractionWarning[];
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

export type Decision = "approved" | "rejected";

export type DecisionResponse = {
  audit_log_id: number;
  event_type: string;
};

export type ChatResponse = {
  thread_id: string;
  message: string;
  routed_to: string | null;
};

export type AgentInstance = {
  id: number;
  template_name: string;
  display_name: string;
  description: string;
  instructions: string | null;
  status: "draft" | "deployed";
  included_in_chat: boolean;
  created_at: string;
  updated_at: string;
};

export type UpdateAgentInstanceRequest = {
  display_name?: string;
  description?: string;
  instructions?: string;
  included_in_chat?: boolean;
};

export type AgentDocument = {
  id: number;
  instance_id: number;
  filename: string;
  chunk_count: number;
  created_at: string;
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

  runAgentReport: (agentId: number) =>
    request<RunReportResponse>(`/agents/${agentId}/reports/run`, { method: "POST" }),

  submitDecision: (
    workflowName: string,
    threadId: string,
    decision: Decision,
    actor: string,
    comment: string | null,
  ) =>
    request<DecisionResponse>(`/reports/${workflowName}/${threadId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, actor, comment }),
    }),

  chat: (message: string, threadId: string | null) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify({ message, thread_id: threadId }),
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

  uploadDocument: (agentId: number, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
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
};
