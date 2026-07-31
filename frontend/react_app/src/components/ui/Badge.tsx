import clsx from "clsx";
import type { ReactNode } from "react";
import "./Badge.css";

type Variant = "neutral" | "primary" | "success" | "warning";

export function Badge({
  children,
  variant = "neutral",
  className,
}: {
  children: ReactNode;
  variant?: Variant;
  className?: string;
}) {
  return <span className={clsx("ui-badge", `ui-badge-${variant}`, className)}>{children}</span>;
}
