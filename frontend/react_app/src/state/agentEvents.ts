type Listener = () => void;

const listeners = new Set<Listener>();

/** Call after creating, deploying, deleting, or renaming an agent instance —
 * lets the persistent sidebar (which only fetches once on app load, since it
 * wraps every page instead of remounting per route) know to refresh. */
export function notifyAgentsChanged(): void {
  listeners.forEach((listener) => listener());
}

export function onAgentsChanged(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
