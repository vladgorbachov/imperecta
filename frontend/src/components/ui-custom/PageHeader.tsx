import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
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
 * Page header with display font, large title.
 * Responsive: actions stack below title on mobile.
 */
export function PageHeader({ title, description, actions, className }: PageHeaderProps) {
  const { t } = useTranslation();

  return (
    <div
      className={cn(
        "flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between",
        className
      )}
    >
      <div className="space-y-1">
        <h1 className="font-display text-xl font-bold tracking-tight sm:text-2xl md:text-3xl">
          {t(title)}
        </h1>
        {description && (
          <p className="text-sm text-muted-foreground dark:text-muted-foreground">
            {t(description)}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>
      )}
    </div>
  );
}
