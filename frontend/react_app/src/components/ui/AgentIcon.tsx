import { Bot, Boxes, LineChart, ScrollText, Shield, Sparkles, Workflow } from "lucide-react";
import "./AgentIcon.css";

const ICONS = [Bot, Shield, ScrollText, LineChart, Boxes, Workflow, Sparkles];
const PALETTE = ["#0f62fe", "#8a3ffc", "#007d79", "#d02670", "#fa4d56", "#08bdba", "#8e6a00"];

function hashString(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i++) {
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0;
  }
  return hash;
}

// Deterministic icon + tint per agent/template name — gives the catalog
// visual variety without needing a real icon per template.
export function AgentIcon({ seed, size = 40 }: { seed: string; size?: number }) {
  const hash = hashString(seed);
  const Icon = ICONS[hash % ICONS.length];
  const color = PALETTE[hash % PALETTE.length];
  return (
    <div
      className="agent-icon"
      style={{ width: size, height: size, background: `${color}1a`, color }}
    >
      <Icon size={Math.round(size * 0.52)} strokeWidth={2} />
    </div>
  );
}
