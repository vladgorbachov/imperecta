/**
 * /trust — one page that states how the product handles third-party data:
 * attribution, no export, crawler identity and opt-out, sanctions
 * compliance, contact. Short factual copy mirroring what the code enforces;
 * counsel may extend it via the legal documents.
 */

import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Database, Link2, Lock, Scale, ShieldBan } from "lucide-react";
import { PublicPageShell } from "@/pages/legal/PublicPageShell";
import { BLOCKED_CONTACT_EMAIL } from "@/pages/BlockedCountryPage";

const SECTIONS = [
  { key: "attribution", icon: Link2, link: "/legal/data-sources" },
  { key: "noExport", icon: Lock, link: "/legal/aup" },
  { key: "crawler", icon: Database, link: "/bot" },
  { key: "sanctions", icon: ShieldBan, link: "/legal/terms" },
] as const;

const SECTION_TITLES: Record<(typeof SECTIONS)[number]["key"], string> = {
  attribution: "trust.attribution.title",
  noExport: "trust.noExport.title",
  crawler: "trust.crawler.title",
  sanctions: "trust.sanctions.title",
};

const SECTION_BODIES: Record<(typeof SECTIONS)[number]["key"], string> = {
  attribution: "trust.attribution.body",
  noExport: "trust.noExport.body",
  crawler: "trust.crawler.body",
  sanctions: "trust.sanctions.body",
};

export function TrustPage() {
  const { t } = useTranslation();
  return (
    <PublicPageShell title={t("legal.trust")}>
      <p className="text-muted-foreground">{t("trust.intro")}</p>
      <div className="grid gap-4 sm:grid-cols-2">
        {SECTIONS.map((section) => {
          const Icon = section.icon;
          return (
            <section
              key={section.key}
              className="surface-base space-y-2 rounded-xl p-4"
              data-testid={`trust-${section.key}`}
            >
              <h2 className="flex items-center gap-2 text-base font-semibold">
                <Icon className="size-4 text-[var(--accent)]" aria-hidden />
                {t(SECTION_TITLES[section.key])}
              </h2>
              <p className="text-muted-foreground">{t(SECTION_BODIES[section.key])}</p>
              <Link to={section.link} className="text-xs text-[var(--accent)] hover:underline">
                {t("trust.readMore")}
              </Link>
            </section>
          );
        })}
      </div>
      <section className="space-y-1">
        <h2 className="flex items-center gap-2 text-base font-semibold">
          <Scale className="size-4 text-[var(--accent)]" aria-hidden />
          {t("trust.contact.title")}
        </h2>
        <p className="text-muted-foreground">
          {t("trust.contact.body")}{" "}
          <a className="text-[var(--accent)] underline" href={`mailto:${BLOCKED_CONTACT_EMAIL}`}>
            {BLOCKED_CONTACT_EMAIL}
          </a>
        </p>
      </section>
    </PublicPageShell>
  );
}
