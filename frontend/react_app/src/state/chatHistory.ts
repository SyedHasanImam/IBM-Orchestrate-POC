import { useSyncExternalStore } from "react";

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  routedTo?: string | null;
};

export interface ChatHistoryState {
  threadId: string | null;
  messages: ChatMessage[];
  input: string;
  loading: boolean;
  error: string | null;
}

const EMPTY_STATE: ChatHistoryState = {
  threadId: null,
  messages: [],
  input: "",
  loading: false,
  error: null,
};

let state: ChatHistoryState = EMPTY_STATE;
const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((listener) => listener());
}

export function getChatHistory(): ChatHistoryState {
  return state;
}

export function updateChatHistory(patch: Partial<ChatHistoryState>): void {
  state = { ...state, ...patch };
  notify();
}

export function resetChatHistory(): void {
  state = EMPTY_STATE;
  notify();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Homepage supervisor chat survives navigating away and back — the
 * conversation lives here rather than in ChatPage's own state, which would
 * otherwise be wiped every time the route unmounts. */
export function useChatHistory(): ChatHistoryState {
  return useSyncExternalStore(subscribe, getChatHistory);
}
