import { AlertTriangle, type LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface ErrorStateProps {
  /** i18n key for title */
  title: string;
  /** i18n key for description (optional) */
  description?: string;
  /** Optional retry action */
  retry?: { label: string; onClick: () => void };
  /** Icon override; defaults to AlertTriangle */
  icon?: LucideIcon;
  /** Destructive panel wrapper; default true for contained error UI */
  bordered?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Centered error state: destructive icon/title, optional description, optional retry.
 */
export function ErrorState({
  title,
  description,
  retry,
  icon: Icon = AlertTriangle,
  bordered = true,
  className,
}: ErrorStateProps) {
  const { t } = useTranslation();

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 px-4 py-10 text-center",
        "animate-in fade-in-0 slide-in-from-bottom-2 duration-300",
        bordered && "rounded-xl border border-destructive/40 bg-destructive/10",
        className
      )}
    >
      <Icon className="size-10 shrink-0 text-destructive" />
      <div className="space-y-1.5">
        <h3 className="text-base font-semibold text-destructive">{t(title)}</h3>
        {description && (
          <p className="max-w-sm text-sm text-muted-foreground">{t(description)}</p>
        )}
      </div>
      {retry && (
        <Button variant="outline" onClick={retry.onClick}>
          {t(retry.label)}
        </Button>
      )}
    </div>
  );
}
