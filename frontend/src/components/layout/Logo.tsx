/**
 * Imperecta brand mark + wordmark, rendered as inline SVG.
 *
 * Mark: rounded square with a cyan→blue→indigo gradient, a soft glow,
 * and a small white spark path inside. No external image assets are used.
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
        className="grid size-[30px] shrink-0 place-items-center rounded-[9px]"
        style={{
          background: "linear-gradient(135deg, #22d3ee, #3b82f6 55%, #6366f1)",
          boxShadow: "0 6px 20px -8px rgba(56,130,246,0.8)",
        }}
      >
        <svg
          width="17"
          height="17"
          viewBox="0 0 24 24"
          fill="none"
          stroke="#fff"
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
          className="text-[16px] font-bold tracking-[-0.01em] text-[var(--foreground)]"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Imperecta
        </span>
      )}
    </span>
  );
}
