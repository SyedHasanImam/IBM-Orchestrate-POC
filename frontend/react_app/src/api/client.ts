const BASE_URL = import.meta.env.VITE_BACKEND_API_URL ?? "http://localhost:8000";

export type CatalogEntry = {
  name: string;
  description: string;
  version: string;
  updated_at: string;
};

export type RunReportResponse = {
  thread_id: string;
  report: string;
  message: string;
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

export const api = {
  getCatalog: () => request<CatalogEntry[]>("/catalog"),

  runReport: (workflowName: string) =>
    request<RunReportResponse>(`/reports/${workflowName}/run`, {
      method: "POST",
    }),

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
};
