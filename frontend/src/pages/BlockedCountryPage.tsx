/**
 * HTTP 451 landing: the API refused the request because the caller's
 * country is on the blocked list (sanctions / product exclusions).
 * Fixed wording by design — no country, no details, only a contact.
 */

import { useTranslation } from "react-i18next";
import { ShieldBan } from "lucide-react";
import { Logo } from "@/components/layout/Logo";

export const BLOCKED_CONTACT_EMAIL = "info@imperecta.com";

export function BlockedCountryPage() {
  const { t } = useTranslation();

  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center gap-6 p-6 text-center"
      style={{ background: "var(--background)", color: "var(--foreground)" }}
      data-testid="blocked-country-page"
    >
      <Logo />
      <ShieldBan className="size-10 text-muted-foreground" aria-hidden />
      <div className="max-w-md space-y-3">
        <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">
          {t("blocked.title")}
        </h1>
        <p className="text-sm leading-relaxed text-muted-foreground">{t("blocked.body")}</p>
        <p className="text-sm">
          {t("blocked.contact")}{" "}
          <a className="text-[var(--accent)] underline" href={`mailto:${BLOCKED_CONTACT_EMAIL}`}>
            {BLOCKED_CONTACT_EMAIL}
          </a>
        </p>
      </div>
      <p className="label-mono">HTTP 451</p>
    </div>
  );
}
