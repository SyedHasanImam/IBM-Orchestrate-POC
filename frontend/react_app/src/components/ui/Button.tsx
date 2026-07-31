import clsx from "clsx";
import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";
import "./Button.css";

type Variant = "primary" | "secondary" | "danger" | "ghost";
type Size = "sm" | "md";

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }
>(({ variant = "secondary", size = "md", className, ...props }, ref) => (
  <button
    ref={ref}
    className={clsx("ui-btn", `ui-btn-${variant}`, size === "sm" && "ui-btn-sm", className)}
    {...props}
  />
));

Button.displayName = "Button";
