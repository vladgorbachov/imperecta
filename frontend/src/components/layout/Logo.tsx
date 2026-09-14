/**
 * Imperecta brand mark + wordmark, rendered as inline SVG.
 *
 * Mark: rounded square in the accent gradient (token-based) with a small
 * spark path inside. No external image assets are used.
 * The wordmark is hidden when `collapsed` is true (used by the rail sidebar).
 */

import { cn } from "@/lib/utils";

interface LogoProps {
  collapsed?: boolean;
  className?: string;
}

export function Logo({ collapsed = false, className }: LogoProps) {
  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <span
        className="grid size-7 shrink-0 place-items-center rounded-lg"
        style={{
          background: "linear-gradient(135deg, var(--accent-dim), var(--accent))",
        }}
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="var(--primary-foreground)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden
        >
          <path d="M4 13l4-5 4 3 4-7" />
        </svg>
      </span>
      {!collapsed && (
        <span
          className="text-[17px] font-semibold tracking-[-0.01em] text-[var(--foreground)]"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Imperecta
        </span>
      )}
    </span>
  );
}
