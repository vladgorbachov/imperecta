/**
 * Digests page - placeholder.
 *
 * The digests module on the backend is intentionally empty (DA1). No data
 * source exists yet, so this page renders an honest "coming soon" empty state
 * instead of calling deleted endpoints. Reuses existing i18n keys
 * `digests.strategicComingSoon` / `digests.strategicComingSoonDesc`.
 */

import { FileText } from "lucide-react";

import { EmptyState } from "@/components/ui-custom/EmptyState";
import { PageHeader } from "@/components/ui-custom/PageHeader";

export function DigestsPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="nav.digests" />
      <EmptyState
        icon={FileText}
        title="digests.strategicComingSoon"
        description="digests.strategicComingSoonDesc"
      />
    </div>
  );
}
