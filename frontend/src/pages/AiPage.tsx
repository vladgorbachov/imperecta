/**
 * AI Analyst page placeholder.
 * Section under development.
 */

import { useTranslation } from "react-i18next";
import { Bot } from "lucide-react";

export function AiPage() {
  const { t } = useTranslation();

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
      <Bot className="mb-4 size-16 text-muted-foreground" />
      <h1 className="font-display text-2xl font-bold tracking-tight">
        {t("nav.ai")}
      </h1>
      <p className="mt-2 text-muted-foreground">
        {t("common.underDevelopment")}
      </p>
    </div>
  );
}
