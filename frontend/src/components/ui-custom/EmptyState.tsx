import type { LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface EmptyStateProps {
  /** i18n key for title */
  title: string;
  /** i18n key for description */
  description: string;
  /** Optional CTA button */
  action?: { label: string; onClick: () => void };
  /** Optional large icon (muted) */
  icon?: LucideIcon;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Centered empty state: large muted icon, title, description, optional CTA button.
 */
export function EmptyState({
  title,
  description,
  action,
  icon: Icon,
  className,
}: EmptyStateProps) {
  const { t } = useTranslation();

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-4 px-4 py-12 text-center",
        className
      )}
    >
      {Icon && (
        <Icon className="size-16 shrink-0 text-muted-foreground dark:text-muted-foreground" />
      )}
      <div className="space-y-2">
        <h3 className="text-lg font-semibold">{t(title)}</h3>
        <p className="max-w-sm text-sm text-muted-foreground dark:text-muted-foreground">
          {t(description)}
        </p>
      </div>
      {action && (
        <Button onClick={action.onClick}>{t(action.label)}</Button>
      )}
    </div>
  );
}
