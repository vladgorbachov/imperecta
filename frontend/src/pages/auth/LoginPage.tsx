/**
 * Login page: split layout with brand panel, form with email/password.
 * Inline validation on blur. Integrates with POST /auth/login.
 */

import { useState } from "react";
import { Link, useNavigate, useLocation, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Mail, Lock, Eye, EyeOff, Loader2 } from "lucide-react";
import { useAuthStore } from "@/stores/authStore";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const login = useAuthStore((s) => s.login);
  const accessToken = useAuthStore((s) => s.accessToken);

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname ?? "/dashboard";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [emailError, setEmailError] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [submitError, setSubmitError] = useState("");
  const [loading, setLoading] = useState(false);

  if (accessToken) {
    return <Navigate to={from} replace />;
  }

  const validateEmail = (value: string) => {
    if (!value.trim()) return t("auth.fieldRequired");
    if (!EMAIL_REGEX.test(value)) return t("auth.emailInvalid");
    return "";
  };

  const validatePassword = (value: string) => {
    if (!value) return t("auth.fieldRequired");
    return "";
  };

  const handleEmailBlur = () => setEmailError(validateEmail(email));
  const handlePasswordBlur = () => setPasswordError(validatePassword(password));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const eErr = validateEmail(email);
    const pErr = validatePassword(password);
    setEmailError(eErr);
    setPasswordError(pErr);
    if (eErr || pErr) return;

    setSubmitError("");
    setLoading(true);
    try {
      const result = await login({ email, password, remember_me: rememberMe });
      if (result.forcePasswordChange) {
        navigate("/change-password", { replace: true });
      } else {
        navigate(from, { replace: true });
      }
    } catch (err: unknown) {
      const message =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : t("auth.loginError");
      setSubmitError(typeof message === "string" ? message : t("auth.loginError"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout>
      <form onSubmit={handleSubmit} className="space-y-6">
        <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">
          {t("auth.loginTitle")}
        </h1>

        {submitError && (
          <div className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive dark:bg-destructive/20 dark:text-destructive">
            {submitError}
          </div>
        )}

        <div className="space-y-2">
          <label htmlFor="email" className="text-sm font-medium">
            {t("auth.email")}
          </label>
          <div className="relative">
            <Mail className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground dark:text-muted-foreground" />
            <Input
              id="email"
              type="email"
              placeholder={t("auth.emailPlaceholder")}
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                setEmailError("");
              }}
              onBlur={handleEmailBlur}
              autoComplete="email"
              className={cn(
                "pl-9",
                emailError && "border-destructive focus-visible:ring-destructive"
              )}
            />
          </div>
          {emailError && (
            <p className="text-xs text-destructive dark:text-destructive">{emailError}</p>
          )}
        </div>

        <div className="space-y-2">
          <label htmlFor="password" className="text-sm font-medium">
            {t("auth.password")}
          </label>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground dark:text-muted-foreground" />
            <Input
              id="password"
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                setPasswordError("");
              }}
              onBlur={handlePasswordBlur}
              autoComplete="current-password"
              className={cn(
                "pr-9 pl-9",
                passwordError && "border-destructive focus-visible:ring-destructive"
              )}
            />
            <button
              type="button"
              onClick={() => setShowPassword((s) => !s)}
              className="absolute right-1 top-1/2 min-h-10 min-w-10 -translate-y-1/2 rounded-md p-2 text-muted-foreground hover:text-foreground dark:text-muted-foreground dark:hover:text-foreground"
              aria-label={showPassword ? t("common.hidePassword") : t("common.showPassword")}
            >
              {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
          {passwordError && (
            <p className="text-xs text-destructive dark:text-destructive">{passwordError}</p>
          )}
        </div>

        <div className="flex items-center justify-between">
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <Checkbox checked={rememberMe} onCheckedChange={(v) => setRememberMe(v === true)} />
            {t("auth.login.rememberMe")}
          </label>
          <Link
            to="/forgot-password"
            className="text-sm text-primary hover:underline dark:text-primary"
          >
            {t("auth.forgotPassword")}
          </Link>
        </div>

        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            t("auth.submitLogin")
          )}
        </Button>

        <div className="space-y-4">
          <div className="relative">
            <Separator />
            <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-background px-2 text-xs text-muted-foreground dark:bg-background dark:text-muted-foreground">
              {t("auth.or")}
            </span>
          </div>
          <p className="text-center text-sm text-muted-foreground dark:text-muted-foreground">
            {t("auth.noAccount")}{" "}
            <Link to="/register" className="font-medium text-primary hover:underline dark:text-primary">
              {t("auth.register")}
            </Link>
          </p>
        </div>
      </form>
    </AuthLayout>
  );
}
