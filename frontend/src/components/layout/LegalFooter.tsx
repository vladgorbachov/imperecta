/**
 * Legal links shown on every public surface (auth pages, legal pages) and
 * in the app sidebar footer: Terms, Privacy, AUP, Data Sources & Bot
 * Policy, Trust. Texts arrive from counsel (F8); the routes exist now.
 */

import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";

const LEGAL_LINKS = [
  { key: "legal.terms", to: "/legal/terms" },
  { key: "legal.privacy", to: "/legal/privacy" },
  { key: "legal.aup", to: "/legal/aup" },
  { key: "legal.dataSources", to: "/legal/data-sources" },
  { key: "legal.trust", to: "/trust" },
] as const;

export function LegalFooter({ className, compact = false }: { className?: string; compact?: boolean }) {
  const { t } = useTranslation();
  return (
    <nav
      aria-label={t("legal.footerLabel")}
      className={cn(
        "flex flex-wrap gap-x-3 gap-y-1 text-2xs text-muted-foreground",
        compact ? "justify-center" : "justify-start",
        className,
      )}
    >
      {LEGAL_LINKS.map((link) => (
        <Link key={link.to} to={link.to} className="hover:text-[var(--foreground)] hover:underline">
          {t(link.key)}
        </Link>
      ))}
    </nav>
  );
}
