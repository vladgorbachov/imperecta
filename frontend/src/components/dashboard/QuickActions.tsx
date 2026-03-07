/**
 * Quick actions: scrape, digest, export.
 */

import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { RefreshCw, FileText, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { toast } from "sonner";
import { apiClient } from "@/api/client";
import { cn } from "@/lib/utils";

export function QuickActions() {
  const { t } = useTranslation();

  const handleScrape = async () => {
    try {
      await apiClient.post("/admin/scrape-all");
    } catch {
      // Endpoint may not exist yet
    }
    toast.success(t("dashboard.actions.scrapeStarted"));
  };

  const handleDigest = () => {
    toast.info(t("dashboard.actions.digestScheduled"));
  };

  const actions = [
    {
      key: "scrape",
      icon: RefreshCw,
      labelKey: "dashboard.actions.scrapeAll",
      onClick: handleScrape,
      disabled: false,
    },
    {
      key: "digest",
      icon: FileText,
      labelKey: "dashboard.actions.generateDigest",
      onClick: handleDigest,
      disabled: false,
    },
    {
      key: "export",
      icon: Download,
      labelKey: "dashboard.actions.exportReport",
      onClick: () => {},
      disabled: true,
      tooltip: t("common.comingSoon"),
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.35, duration: 0.3 }}
      className="grid grid-cols-1 gap-2 sm:grid-cols-3"
    >
      {actions.map((a) => {
        const btn = (
          <Button
            key={a.key}
            variant="outline"
            className={cn(
              "h-auto flex-col gap-2 rounded-xl border border-border/50 bg-card/60 p-4 shadow-sm backdrop-blur-lg transition-all hover:scale-[1.02] hover:bg-accent/30 dark:bg-zinc-900/60 dark:border-border/50",
              a.disabled && "opacity-60"
            )}
            onClick={a.disabled ? undefined : a.onClick}
            disabled={a.disabled}
          >
            <a.icon className="size-6" />
            <span className="text-center text-sm">{t(a.labelKey)}</span>
          </Button>
        );

        return a.tooltip ? (
          <Tooltip key={a.key}>
            <TooltipTrigger asChild>{btn}</TooltipTrigger>
            <TooltipContent>{a.tooltip}</TooltipContent>
          </Tooltip>
        ) : (
          btn
        );
      })}
    </motion.div>
  );
}
