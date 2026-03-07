/**
 * AI Agent panel with preset questions and markdown responses.
 * TODO: connect to POST /api/ai/chat
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Bot, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

const MOCK_RESPONSES: Record<string, string> = {
  market: `**Market overview (last 7 days):**
- Ozon: average price drop **-2.3%** on electronics
- Wildberries: **+1.8%** on gadgets, promo activity increased
- 3 competitors lowered iPhone 15 prices by 8–12%
- Recommendation: monitor Ozon promos this week`,

  price: `**Price recommendations:**
- **iPhone 15**: Consider -5% to match Ozon flash sale
- **Samsung S24**: Current price optimal, no action
- **MacBook Air**: 2 competitors 3% below you — optional -2% adjustment
- Overall margin impact: -0.4% if all applied`,

  compare: `**Week-over-week comparison:**
| Metric        | Last week | This week | Δ    |
|---------------|-----------|-----------|------|
| Avg my price  | 45,200 ₽  | 45,100 ₽  | -0.2% |
| Avg competitors| 43,800 ₽  | 43,200 ₽  | -1.4% |
| Price gap     | +3.2%     | +4.4%     | +1.2% |

Competitors are undercutting more aggressively. Consider targeted promos.`,
};

export function AIInsightsPanel() {
  const { t } = useTranslation();
  const [activeQuestion, setActiveQuestion] = useState<string | null>(null);

  const presets = [
    { key: "market", labelKey: "dashboard.ai.marketQuestion" },
    { key: "price", labelKey: "dashboard.ai.priceRecommendation" },
    { key: "compare", labelKey: "dashboard.ai.compareWeek" },
  ];

  const renderMarkdown = (text: string) => {
    const lines = text.split("\n");
    return lines.map((line, i) => {
      const trimmed = line.trim();
      if (!trimmed) return <br key={i} />;
      if (trimmed.startsWith("**") && trimmed.endsWith("**")) {
        return <p key={i} className="font-semibold">{trimmed.replace(/\*\*/g, "")}</p>;
      }
      if (trimmed.startsWith("- ")) {
        const content = trimmed.slice(2);
        const parts = content.split(/(\*\*.+?\*\*)/g);
        return (
          <li key={i} className="ml-4 list-disc">
            {parts.map((p, j) =>
              p.startsWith("**") ? <strong key={j}>{p.replace(/\*\*/g, "")}</strong> : p
            )}
          </li>
        );
      }
      if (trimmed.startsWith("|")) {
        return <pre key={i} className="overflow-x-auto text-xs font-mono">{trimmed}</pre>;
      }
      const parts = trimmed.split(/(\*\*.+?\*\*)/g);
      return (
        <p key={i}>
          {parts.map((p, j) =>
            p.startsWith("**") ? <strong key={j}>{p.replace(/\*\*/g, "")}</strong> : p
          )}
        </p>
      );
    });
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3, duration: 0.3 }}
      className="rounded-xl border border-border/50 bg-card/60 p-4 shadow-sm backdrop-blur-lg dark:bg-zinc-900/60 dark:border-border/50"
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

      {activeQuestion && MOCK_RESPONSES[activeQuestion] && (
        <div className="mt-4 rounded-lg border border-border/50 bg-background/50 p-3 dark:border-border/50">
          <div className="prose prose-sm dark:prose-invert max-w-none space-y-1 text-sm">
            {renderMarkdown(MOCK_RESPONSES[activeQuestion])}
          </div>
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
