import * as Dialog from "@radix-ui/react-dialog";
import { Plus, X } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, type ToolInfo } from "../api/client";
import { formatSlug } from "../utils/format";
import "./AddToolDialog.css";

export function AddToolDialog({
  open,
  onOpenChange,
  excludeToolNames,
  onAdd,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  excludeToolNames: string[];
  onAdd: (toolName: string) => Promise<void>;
}) {
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [addingName, setAddingName] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    api
      .listTools()
      .then(setTools)
      .finally(() => setLoading(false));
  }, [open]);

  const available = tools.filter((tool) => !excludeToolNames.includes(tool.name));

  async function handleAdd(toolName: string) {
    setAddingName(toolName);
    try {
      await onAdd(toolName);
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to add tool.");
    } finally {
      setAddingName(null);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="add-tool-dialog-overlay" />
        <Dialog.Content className="add-tool-dialog-content">
          <div className="add-tool-dialog-header">
            <Dialog.Title className="add-tool-dialog-title">Add a tool</Dialog.Title>
            <Dialog.Close asChild>
              <button type="button" className="add-tool-dialog-close" aria-label="Close">
                <X size={16} />
              </button>
            </Dialog.Close>
          </div>
          <Dialog.Description className="add-tool-dialog-description">
            Choose a tool to give this agent access to, on top of whatever its
            template already includes.
          </Dialog.Description>

          {loading && <p className="add-tool-dialog-empty">Loading…</p>}
          {!loading && available.length === 0 && (
            <p className="add-tool-dialog-empty">
              This agent already has every available tool.
            </p>
          )}

          <div className="add-tool-dialog-list">
            {available.map((tool) => (
              <button
                key={tool.name}
                type="button"
                className="add-tool-dialog-row"
                onClick={() => handleAdd(tool.name)}
                disabled={addingName !== null}
              >
                <div className="add-tool-dialog-row-info">
                  <span className="add-tool-dialog-row-name">{formatSlug(tool.name)}</span>
                  <span className="add-tool-dialog-row-desc">{tool.description}</span>
                </div>
                {addingName === tool.name ? (
                  <span className="add-tool-dialog-row-adding">Adding…</span>
                ) : (
                  <Plus size={15} />
                )}
              </button>
            ))}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
