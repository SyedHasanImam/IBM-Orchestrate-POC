import { useSyncExternalStore } from "react";
import type { DecisionResponse, RunReportResponse } from "../api/client";

export interface ReportRunState {
  runResult: RunReportResponse | null;
  finalized: DecisionResponse | null;
  actor: string;
  comment: string;
  running: boolean;
  deciding: boolean;
  error: string | null;
}

const EMPTY_STATE: ReportRunState = {
  runResult: null,
  finalized: null,
  actor: "",
  comment: "",
  running: false,
  deciding: false,
  error: null,
};

const states = new Map<number, ReportRunState>();
const listeners = new Map<number, Set<() => void>>();

function notify(agentId: number) {
  listeners.get(agentId)?.forEach((listener) => listener());
}

export function getReportRun(agentId: number): ReportRunState {
  return states.get(agentId) ?? EMPTY_STATE;
}

export function updateReportRun(agentId: number, patch: Partial<ReportRunState>): void {
  states.set(agentId, { ...getReportRun(agentId), ...patch });
  notify(agentId);
}

export function resetReportRun(agentId: number): void {
  states.delete(agentId);
  notify(agentId);
}

function subscribe(agentId: number, listener: () => void): () => void {
  if (!listeners.has(agentId)) listeners.set(agentId, new Set());
  const set = listeners.get(agentId)!;
  set.add(listener);
  return () => set.delete(listener);
}

/** Report run state survives navigating away and back — a run kicked off
 * on this agent keeps going, and its result is still there when you return,
 * since the state lives here rather than in the page component. */
export function useReportRun(agentId: number): ReportRunState {
  return useSyncExternalStore(
    (listener) => subscribe(agentId, listener),
    () => getReportRun(agentId),
  );
}
