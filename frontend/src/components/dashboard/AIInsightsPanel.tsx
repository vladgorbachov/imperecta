/**
 * AI Agent panel with preset questions.
 * Connects to POST /api/ai/chat when available.
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Bot, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

export function AIInsightsPanel() {
  const { t } = useTranslation();
  const [activeQuestion, setActiveQuestion] = useState<string | null>(null);

  const presets = [
    { key: "market", labelKey: "dashboard.ai.marketQuestion" },
    { key: "price", labelKey: "dashboard.ai.priceRecommendation" },
    { key: "compare", labelKey: "dashboard.ai.compareWeek" },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3, duration: 0.3 }}
      className="rounded-xl border border-border bg-card p-4 shadow-sm dark:border-border"
    >
      <div className="mb-4 flex items-center gap-2">
        <Bot className="size-5 text-primary" />
        <Sparkles className="size-4 animate-pulse text-primary" />
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          {t("dashboard.ai.title")}
        </h3>
      </div>

      <div className="space-y-2">
        {presets.map((p) => (
          <Button
            key={p.key}
            variant="outline"
            className="w-full justify-start text-left"
            onClick={() => setActiveQuestion(activeQuestion === p.key ? null : p.key)}
          >
            {t(p.labelKey)}
          </Button>
        ))}
      </div>

      {activeQuestion && (
        <div className="mt-4 rounded-lg border border-border bg-muted/30 p-3 dark:border-border">
          <p className="text-sm text-muted-foreground">
            {t("dashboard.ai.useFullAnalyst")}
          </p>
        </div>
      )}

      <Link
        to="/ai"
        className="mt-4 block text-sm font-medium text-primary hover:underline"
      >
        {t("dashboard.ai.openFull")}
      </Link>
    </motion.div>
  );
}
