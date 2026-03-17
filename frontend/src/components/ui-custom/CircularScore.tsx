/**
 * Circular progress for benchmark score 0–100 with gradient color.
 * Low (0–33): green, Mid (34–66): amber, High (67–100): red.
 */

import { cn } from "@/lib/utils";

export interface CircularScoreProps {
  value: number;
  size?: number;
  strokeWidth?: number;
  className?: string;
}

export function CircularScore({
  value,
  size = 48,
  strokeWidth = 4,
  className,
}: CircularScoreProps) {
  const clamped = Math.min(100, Math.max(0, value));
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (clamped / 100) * circumference;

  const strokeColor =
    clamped >= 67
      ? "stroke-red-500 dark:stroke-red-500"
      : clamped >= 34
        ? "stroke-amber-500 dark:stroke-amber-500"
        : "stroke-emerald-500 dark:stroke-emerald-500";

  return (
    <div
      className={cn("relative inline-flex", className)}
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          className="stroke-muted dark:stroke-muted"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className={cn("transition-all duration-500 ease-out", strokeColor)}
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-xs font-bold">
        {Math.round(clamped)}
      </span>
    </div>
  );
}
