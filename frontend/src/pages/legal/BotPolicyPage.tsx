/**
 * /bot — how the Imperecta crawler identifies itself and the opt-out form
 * for source operators (POST /bot/opt-out, no auth). Policy text itself is
 * the Data Sources & Bot Policy document (/legal/data-sources).
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { CheckCircle, Loader2 } from "lucide-react";
import axios from "axios";
import { botApi } from "@/api/bot";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PublicPageShell } from "@/pages/legal/PublicPageShell";
import { cn } from "@/lib/utils";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
/** Host-name shape check only (labels of letters/digits/hyphens, at least one dot). */
function isDomainLike(value: string): boolean {
  const labels = value.split(".");
  if (labels.length < 2) {
    return false;
  }
  return labels.every(
    (label) =>
      label.length >= 1 &&
      label.length <= 63 &&
      /^[a-z0-9-]+$/i.test(label) &&
      !label.startsWith("-") &&
      !label.endsWith("-"),
  );
}

export function BotPolicyPage() {
  const { t } = useTranslation();
  const [domain, setDomain] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [requestId, setRequestId] = useState<string | null | undefined>(undefined);

  const domainValid = isDomainLike(domain.trim());
  const emailValid = EMAIL_REGEX.test(email.trim());
  const canSubmit = domainValid && emailValid && !pending;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!canSubmit) {
      setError(t("bot.optOut.invalid"));
      return;
    }
    setError("");
    setPending(true);
    try {
      const { data } = await botApi.optOut({
        domain: domain.trim().toLowerCase(),
        contact_email: email.trim(),
        message: message.trim().slice(0, 2000) || undefined,
      });
      setRequestId(data?.request_id ?? null);
    } catch (err) {
      const detail = axios.isAxiosError(err)
        ? (err.response?.data as { detail?: unknown } | undefined)?.detail
        : undefined;
      setError(typeof detail === "string" ? detail : t("bot.optOut.failed"));
    } finally {
      setPending(false);
    }
  };

  return (
    <PublicPageShell title={t("bot.title")}>
      <section className="space-y-2">
        <h2 className="text-lg font-semibold">{t("bot.identity.title")}</h2>
        <p className="text-muted-foreground">{t("bot.identity.body")}</p>
        <p>
          <Link to="/legal/data-sources" className="text-[var(--accent)] underline-offset-2 hover:underline">
            {t("legal.dataSources")}
          </Link>
        </p>
      </section>

      <section className="space-y-3" data-testid="bot-opt-out">
        <h2 className="text-lg font-semibold">{t("bot.optOut.title")}</h2>
        <p className="text-muted-foreground">{t("bot.optOut.body")}</p>
        {requestId !== undefined ? (
          <div className="flex items-start gap-3 rounded-md border border-[var(--status-ok-border)] bg-[var(--status-ok-bg)] p-4">
            <CheckCircle className="mt-0.5 size-4 shrink-0 text-[var(--status-ok)]" aria-hidden />
            <div>
              <p>{t("bot.optOut.received")}</p>
              {requestId ? (
                <p className="font-mono text-xs text-muted-foreground">{requestId}</p>
              ) : null}
            </div>
          </div>
        ) : (
          <form onSubmit={(event) => void submit(event)} className="space-y-3">
            <div className="space-y-1.5">
              <label htmlFor="opt-out-domain" className="text-sm font-medium">
                {t("bot.optOut.domain")}
              </label>
              <Input
                id="opt-out-domain"
                value={domain}
                onChange={(event) => setDomain(event.target.value)}
                placeholder="shop.example"
                autoComplete="url"
                className={cn(domain && !domainValid && "border-destructive")}
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="opt-out-email" className="text-sm font-medium">
                {t("bot.optOut.email")}
              </label>
              <Input
                id="opt-out-email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder={t("auth.emailPlaceholder")}
                autoComplete="email"
                className={cn(email && !emailValid && "border-destructive")}
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="opt-out-message" className="text-sm font-medium">
                {t("bot.optOut.message")}
              </label>
              <textarea
                id="opt-out-message"
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                rows={3}
                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              />
            </div>
            {error ? <p className="text-xs text-destructive">{error}</p> : null}
            <Button type="submit" disabled={!canSubmit}>
              {pending ? <Loader2 className="size-4 animate-spin" /> : t("bot.optOut.submit")}
            </Button>
          </form>
        )}
      </section>
    </PublicPageShell>
  );
}
