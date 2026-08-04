import { useSyncExternalStore } from "react";

export type AgentChatMessage =
  | { role: "user" | "assistant"; content: string }
  | {
      role: "approval";
      report: string;
      approvalMessage: string;
      decision: "approved" | "rejected" | null;
    };

export interface AgentChatState {
  threadId: string | null;
  messages: AgentChatMessage[];
  input: string;
  loading: boolean;
  error: string | null;
  // Reviewer identity for an in-flight approval card — kept alongside the
  // rest of this agent's chat state rather than per-message, since only one
  // approval can realistically be pending at a time.
  actor: string;
  comment: string;
  deciding: boolean;
}

const EMPTY_STATE: AgentChatState = {
  threadId: null,
  messages: [],
  input: "",
  loading: false,
  error: null,
  actor: "",
  comment: "",
  deciding: false,
};

const states = new Map<number, AgentChatState>();
const listeners = new Map<number, Set<() => void>>();

function notify(agentId: number) {
  listeners.get(agentId)?.forEach((listener) => listener());
}

export function getAgentChat(agentId: number): AgentChatState {
  return states.get(agentId) ?? EMPTY_STATE;
}

export function updateAgentChat(agentId: number, patch: Partial<AgentChatState>): void {
  states.set(agentId, { ...getAgentChat(agentId), ...patch });
  notify(agentId);
}

function subscribe(agentId: number, listener: () => void): () => void {
  if (!listeners.has(agentId)) listeners.set(agentId, new Set());
  const set = listeners.get(agentId)!;
  set.add(listener);
  return () => set.delete(listener);
}

/** Per-agent chat state survives navigating away and back (Editor <-> its
 * Preview tab, or the agent's own page) — keyed by agentId so each agent's
 * conversation is independent, same external-store pattern as chatHistory.ts. */
export function useAgentChat(agentId: number): AgentChatState {
  return useSyncExternalStore(
    (listener) => subscribe(agentId, listener),
    () => getAgentChat(agentId),
  );
}
