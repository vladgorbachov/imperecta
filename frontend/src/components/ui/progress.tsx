import { type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export interface ProgressProps extends HTMLAttributes<HTMLDivElement> {
  value?: number;
  max?: number;
  /** Bar color: default, warning (>80%), danger (>95%) */
  variant?: "default" | "warning" | "danger";
}

/**
 * Progress bar (0–100). Uses role="progressbar" for accessibility.
 * variant: "warning" = amber, "danger" = red.
 */
export function Progress({
  value = 0,
  max = 100,
  variant = "default",
  className,
  ...props
}: ProgressProps) {
  const percent = Math.min(100, Math.max(0, max > 0 ? (value / max) * 100 : 0));
  const barClass =
    variant === "danger"
      ? "bg-red-500 dark:bg-red-500"
      : variant === "warning"
        ? "bg-amber-500 dark:bg-amber-500"
        : "bg-primary";
  return (
    <div
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      className={cn(
        "relative h-2 w-full overflow-hidden rounded-full bg-muted dark:bg-muted",
        className
      )}
      {...props}
    >
      <div
        className={cn("h-full transition-all duration-300 ease-in-out", barClass)}
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}
