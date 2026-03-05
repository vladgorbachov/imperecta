/**
 * Split layout for auth pages: brand panel (desktop) + form area.
 * Mobile: form only with small logo at top.
 */

import { useTranslation } from "react-i18next";
import { CheckCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";

interface AuthLayoutProps {
  children: React.ReactNode;
  className?: string;
}

export function AuthLayout({ children, className }: AuthLayoutProps) {
  const { t } = useTranslation();

  return (
    <div className="flex min-h-screen flex-col lg:flex-row">
      {/* Brand panel - hidden on mobile, 50% on desktop */}
      <div
        className={cn(
          "relative hidden overflow-hidden lg:flex lg:w-1/2 lg:flex-col lg:justify-between lg:p-12",
          "bg-gradient-to-br from-slate-900 via-slate-800 to-teal-900/80 dark:from-slate-950 dark:via-slate-900 dark:to-teal-950/80"
        )}
      >
        <div className="absolute inset-0 opacity-30">
          <GridPatternSvg />
        </div>
        <div className="relative z-10">
          <Link to="/" className="inline-block">
            <span className="font-display text-2xl font-bold tracking-tight text-white">
              {t("nav.logo")}
            </span>
          </Link>
        </div>
        <div className="relative z-10 space-y-8">
          <p className="max-w-sm text-lg text-slate-200 dark:text-slate-300">
            {t("auth.tagline")}
          </p>
          <ul className="space-y-3">
            {[
              t("auth.feature1"),
              t("auth.feature2"),
              t("auth.feature3"),
            ].map((text, i) => (
              <li key={i} className="flex items-center gap-3 text-slate-200 dark:text-slate-300">
                <CheckCircle className="size-5 shrink-0 text-teal-400 dark:text-teal-400" />
                <span>{text}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Form area - full on mobile, 50% on desktop */}
      <div
        className={cn(
          "flex flex-1 flex-col items-center justify-center p-4 sm:p-6 lg:p-12",
          "bg-background text-foreground",
          className
        )}
      >
        {/* Mobile logo */}
        <div className="mb-6 lg:hidden">
          <Link to="/" className="inline-block">
            <span className="font-display text-xl font-bold tracking-tight text-foreground">
              {t("nav.logo")}
            </span>
          </Link>
        </div>
        <div className="w-full max-w-md">{children}</div>
      </div>
    </div>
  );
}

function GridPatternSvg() {
  return (
    <svg
      className="h-full w-full animate-grid-pulse"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <defs>
        <pattern
          id="grid"
          width="40"
          height="40"
          patternUnits="userSpaceOnUse"
          patternTransform="scale(0.5)"
        >
          <path
            d="M 40 0 L 0 0 0 40"
            fill="none"
            stroke="currentColor"
            strokeWidth="0.5"
            className="text-teal-500/30 dark:text-teal-400/20"
          />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#grid)" />
      <circle cx="20%" cy="30%" r="2" fill="currentColor" className="text-teal-400/20 dark:text-teal-400/10" />
      <circle cx="70%" cy="60%" r="2" fill="currentColor" className="text-teal-400/20 dark:text-teal-400/10" />
      <circle cx="50%" cy="80%" r="1.5" fill="currentColor" className="text-teal-400/15 dark:text-teal-400/10" />
    </svg>
  );
}
