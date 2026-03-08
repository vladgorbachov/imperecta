/**
 * Split layout for auth pages: brand panel (desktop) + form area.
 * Left: gradient, glow blobs, SVG grid. Right: glass-card form.
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
    <div className="flex min-h-screen min-h-[100dvh] flex-col lg:flex-row safe-area-top safe-area-bottom">
      {/* Brand panel — gradient, glow blobs, grid */}
      <div
        className={cn(
          "relative hidden overflow-hidden lg:flex lg:w-1/2 lg:flex-col lg:justify-between lg:p-12"
        )}
        style={{
          background: "linear-gradient(135deg, #0a0e1a 0%, #0d1a2e 50%, #0a1628 100%)",
        }}
      >
        <div
          className="absolute -top-20 -right-20 h-80 w-80 rounded-full opacity-30 blur-[80px]"
          style={{ background: "var(--accent)" }}
        />
        <div
          className="absolute -bottom-20 -left-20 h-60 w-60 rounded-full opacity-20 blur-[60px]"
          style={{ background: "var(--accent2)" }}
        />
        <div className="absolute inset-0 opacity-[0.04]">
          <GridPatternSvg />
        </div>
        <div className="relative z-10">
          <Link to="/" className="inline-block">
            <span
              className="text-2xl font-bold tracking-tight"
              style={{ color: "var(--foreground)", fontFamily: "var(--font-display)" }}
            >
              {t("nav.logo")}
            </span>
          </Link>
        </div>
        <div className="relative z-10 space-y-8">
          <p className="max-w-sm text-lg" style={{ color: "var(--foreground-muted)" }}>
            {t("auth.tagline")}
          </p>
          <ul className="space-y-3">
            {[t("auth.feature1"), t("auth.feature2"), t("auth.feature3")].map((text, i) => (
              <li
                key={i}
                className="flex items-center gap-3"
                style={{ color: "var(--foreground-muted)" }}
              >
                <CheckCircle className="size-5 shrink-0" style={{ color: "var(--accent)" }} />
                <span>{text}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Form area — glass-card centered */}
      <div
        className={cn(
          "flex flex-1 flex-col items-center justify-center px-4 py-6 sm:px-6 sm:py-8 lg:p-12",
          className
        )}
        style={{
          background: "var(--background)",
          color: "var(--foreground)",
        }}
      >
        <div className="mb-4 sm:mb-6 lg:hidden">
          <Link to="/" className="inline-block">
            <span
              className="text-xl font-bold tracking-tight"
              style={{ color: "var(--foreground)", fontFamily: "var(--font-display)" }}
            >
              {t("nav.logo")}
            </span>
          </Link>
        </div>
        <div className="glass-card w-full max-w-md rounded-xl p-6 sm:p-8">{children}</div>
      </div>
    </div>
  );
}

function GridPatternSvg() {
  return (
    <svg
      className="h-full w-full"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <defs>
        <pattern
          id="auth-grid"
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
            style={{ color: "var(--foreground)" }}
          />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#auth-grid)" />
    </svg>
  );
}
