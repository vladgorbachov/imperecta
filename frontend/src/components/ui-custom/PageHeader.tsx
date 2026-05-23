import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";

export interface PageHeaderProps {
  /** i18n key for page title */
  title: string;
  /** Optional i18n key for description */
  description?: string;
  /** Optional action buttons or elements (stack below title on mobile) */
  actions?: ReactNode;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Page header with display font, gradient text (dark) or foreground (light).
 */
export function PageHeader({ title, description, actions, className }: PageHeaderProps) {
  const { t } = useTranslation();
  const { resolvedTheme } = useTheme();
  const isLight = resolvedTheme === "light";

  return (
    <div
      className={cn(
        "flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between",
        className
      )}
    >
      <div className="space-y-0.5">
        <h1
          className="text-lg font-semibold tracking-tight sm:text-xl md:text-2xl"
          style={{
            fontFamily: "var(--font-display)",
            ...(isLight
              ? { color: "var(--foreground)" }
              : {
                  background: "linear-gradient(135deg, var(--foreground), var(--foreground-muted))",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  backgroundClip: "text",
                }),
          }}
        >
          {t(title)}
        </h1>
        {description && (
          <p className="text-xs" style={{ color: "var(--foreground-muted)" }}>
            {t(description)}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex shrink-0 flex-wrap gap-1.5">{actions}</div>
      )}
    </div>
  );
}
