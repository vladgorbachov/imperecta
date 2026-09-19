/**
 * Chrome for the public legal / trust pages: logo, title, optional version
 * line, content column and the legal footer. No app navigation — these
 * pages are reachable without a session.
 */

import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { LegalFooter } from "@/components/layout/LegalFooter";
import { Logo } from "@/components/layout/Logo";

export interface PublicPageShellProps {
  title: string;
  meta?: ReactNode;
  children: ReactNode;
}

export function PublicPageShell({ title, meta, children }: PublicPageShellProps) {
  const { t } = useTranslation();
  return (
    <div
      className="flex min-h-screen flex-col"
      style={{ background: "var(--background)", color: "var(--foreground)" }}
    >
      <header className="flex items-center justify-between border-b border-[var(--glass-border)] px-5 py-3">
        <Link to="/" aria-label={t("nav.logo")}>
          <Logo />
        </Link>
        <Link to="/login" className="text-sm text-[var(--accent)] hover:underline">
          {t("auth.login")}
        </Link>
      </header>
      <main className="mx-auto w-full max-w-3xl flex-1 px-5 py-10">
        <h1 className="font-display text-3xl font-bold tracking-tight">{title}</h1>
        {meta ? <div className="mt-2 text-xs text-muted-foreground">{meta}</div> : null}
        <div className="mt-8 space-y-6 text-sm leading-relaxed">{children}</div>
      </main>
      <footer className="border-t border-[var(--glass-border)] px-5 py-4">
        <LegalFooter compact />
      </footer>
    </div>
  );
}
