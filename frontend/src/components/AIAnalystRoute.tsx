/**
 * Route guard for AI Analyst. Renders locked state when user lacks entitlement.
 */

import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Zap, Lock } from "lucide-react";
import { useEntitlements } from "@/hooks/useEntitlements";
import { AIAnalystPage } from "@/pages/AIAnalystPage";
import { Button } from "@/components/ui/button";

export function AIAnalystRoute() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { hasAiAnalyst } = useEntitlements();

  if (hasAiAnalyst) {
    return <AIAnalystPage />;
  }

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-6 px-4">
      <div
        className="flex size-20 items-center justify-center rounded-2xl"
        style={{
          background: "var(--glass-bg)",
          border: "1px solid var(--glass-border)",
        }}
      >
        <Lock className="size-10 text-muted-foreground" />
      </div>
      <div className="max-w-md space-y-2 text-center">
        <h2 className="text-xl font-semibold">{t("ai.lockedTitle")}</h2>
        <p className="text-sm text-muted-foreground dark:text-muted-foreground">
          {t("ai.lockedDescription")}
        </p>
      </div>
      <Button
        size="lg"
        onClick={() => navigate("/settings")}
        style={{
          background: "linear-gradient(135deg, var(--accent-dim), var(--accent))",
          border: "none",
          color: "var(--primary-foreground)",
        }}
      >
        <Zap className="mr-2 size-4" />
        {t("settings.upgradePlan")}
      </Button>
    </div>
  );
}
