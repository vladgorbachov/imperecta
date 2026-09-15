/**
 * Client alerts stream — latest alert events on the Overview dashboard.
 * Backend pending (alerts events feed, see docs/FRONTEND_BACKEND_REQUESTS.md);
 * until it lands this renders the honest empty state only. No mock data.
 */

import { useTranslation } from "react-i18next";
import { Bell } from "lucide-react";
import { EmptyState } from "@/components/ui-custom/EmptyState";

export function AlertsStreamWidget() {
  const { t } = useTranslation();

  return (
    <div className="surface-base flex h-full min-w-0 flex-col rounded-xl p-3.5">
      <div className="mb-3">
        <h3 className="label-mono !text-[var(--foreground)]">{t("dashboard.alerts.title")}</h3>
        <p className="mt-1 text-2xs text-muted-foreground">{t("dashboard.alerts.subtitle")}</p>
      </div>
      <EmptyState
        title="dashboard.alerts.empty"
        description="dashboard.alerts.emptyHint"
        icon={Bell}
        className="py-6"
      />
    </div>
  );
}
