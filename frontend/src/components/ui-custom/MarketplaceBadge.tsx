import { cn } from "@/lib/utils";

export interface MarketplaceBadgeProps {
  /** Marketplace identifier or name from API */
  marketplace: string;
  /** Badge size */
  size?: "sm" | "md";
  /** Additional CSS classes */
  className?: string;
}

/** Generate consistent color from string (for any marketplace). */
function hashToColor(s: string): { bg: string; glow: string } {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (h << 5) - h + s.charCodeAt(i);
    h |= 0;
  }
  const hue = Math.abs(h % 360);
  const bg = `hsl(${hue}, 65%, 45%)`;
  const glow = `hsla(${hue}, 65%, 45%, 0.3)`;
  return { bg, glow };
}

/** Display name: use as-is, or title-case if looks like id (snake_case). */
function displayName(s: string): string {
  if (!s) return "";
  if (s.includes("_")) {
    return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }
  return s;
}

export function MarketplaceBadge({ marketplace, size = "md", className }: MarketplaceBadgeProps) {
  const token = hashToColor(marketplace);
  const name = displayName(marketplace);
  const sizeClasses = size === "sm" ? "px-1.5 py-0 text-xs" : "px-2 py-0.5 text-sm";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border font-medium",
        sizeClasses,
        className
      )}
      style={{
        background: `${token.bg}26`,
        borderColor: `${token.bg}66`,
        color: token.bg,
        boxShadow: `0 0 8px ${token.glow}`,
      }}
    >
      {name}
    </span>
  );
}
