import * as AlertDialog from "@radix-ui/react-alert-dialog";
import { useState } from "react";
import { Button } from "./Button";
import "./ConfirmDialog.css";

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  danger = false,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => Promise<void> | void;
}) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleConfirm(e: React.MouseEvent<HTMLButtonElement>) {
    // Radix closes an AlertDialog.Action on click by default — prevent that
    // so we can show a loading state and only close after the (async)
    // action actually succeeds.
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await onConfirm();
      setSubmitting(false);
      onOpenChange(false);
    } catch (err) {
      setSubmitting(false);
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  return (
    <AlertDialog.Root
      open={open}
      onOpenChange={(next) => {
        if (!submitting) onOpenChange(next);
      }}
    >
      <AlertDialog.Portal>
        <AlertDialog.Overlay className="confirm-dialog-overlay" />
        <AlertDialog.Content className="confirm-dialog-content">
          <AlertDialog.Title className="confirm-dialog-title">{title}</AlertDialog.Title>
          <AlertDialog.Description className="confirm-dialog-description">
            {description}
          </AlertDialog.Description>

          {error && <p className="confirm-dialog-error">{error}</p>}

          <div className="confirm-dialog-actions">
            <AlertDialog.Cancel asChild>
              <Button variant="secondary" disabled={submitting}>
                {cancelLabel}
              </Button>
            </AlertDialog.Cancel>
            <AlertDialog.Action asChild onClick={handleConfirm}>
              <Button variant={danger ? "danger" : "primary"} disabled={submitting}>
                {submitting ? "Working…" : confirmLabel}
              </Button>
            </AlertDialog.Action>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  );
}
