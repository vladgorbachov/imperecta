/**
 * Register page: split layout with brand panel, form with name/email/password.
 * Password strength bar. Inline validation. Integrates with POST /auth/register.
 */

import { useState } from "react";
import { Link, useNavigate, useLocation, Navigate } from "react-router-dom";
import { getReturnPath } from "@/lib/routes";
import { useTranslation } from "react-i18next";
import { User, Mail, Lock, Eye, EyeOff, Loader2 } from "lucide-react";
import { useAuthStore } from "@/stores/authStore";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type PasswordStrength = "weak" | "medium" | "strong";

function getPasswordStrength(pwd: string): PasswordStrength {
  if (!pwd) return "weak";
  let score = 0;
  if (pwd.length >= 8) score++;
  if (pwd.length >= 12) score++;
  if (/[a-z]/.test(pwd) && /[A-Z]/.test(pwd)) score++;
  if (/\d/.test(pwd)) score++;
  if (/[^a-zA-Z0-9]/.test(pwd)) score++;
  if (score <= 2) return "weak";
  if (score <= 4) return "medium";
  return "strong";
}

export function RegisterPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const register = useAuthStore((s) => s.register);
  const accessToken = useAuthStore((s) => s.accessToken);

  const returnPath = getReturnPath(
    new URLSearchParams(location.search),
    location.state as { from?: { pathname: string } } | undefined
  );

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [nameError, setNameError] = useState("");
  const [emailError, setEmailError] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [confirmError, setConfirmError] = useState("");
  const [submitError, setSubmitError] = useState("");
  const [loading, setLoading] = useState(false);

  if (accessToken) {
    return <Navigate to={returnPath} replace />;
  }

  const passwordStrength = getPasswordStrength(password);
  const strengthPercent =
    passwordStrength === "weak" ? 33 : passwordStrength === "medium" ? 66 : 100;
  const strengthKey =
    passwordStrength === "weak"
      ? "auth.passwordWeak"
      : passwordStrength === "medium"
        ? "auth.passwordMedium"
        : "auth.passwordStrong";

  const validateName = (value: string) => {
    if (!value.trim()) return t("auth.fieldRequired");
    return "";
  };

  const validateEmail = (value: string) => {
    if (!value.trim()) return t("auth.fieldRequired");
    if (!EMAIL_REGEX.test(value)) return t("auth.emailInvalid");
    return "";
  };

  const validatePassword = (value: string) => {
    if (!value) return t("auth.fieldRequired");
    if (value.length < 8) return t("auth.fieldRequired");
    return "";
  };

  const validateConfirm = (value: string) => {
    if (!value) return t("auth.fieldRequired");
    const matches = value.length === password.length && value === password;
    if (!matches) return t("auth.passwordMismatch");
    return "";
  };

  const handleNameBlur = () => setNameError(validateName(name));
  const handleEmailBlur = () => setEmailError(validateEmail(email));
  const handlePasswordBlur = () => setPasswordError(validatePassword(password));
  const handleConfirmBlur = () => setConfirmError(validateConfirm(confirmPassword));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const nErr = validateName(name);
    const eErr = validateEmail(email);
    const pErr = validatePassword(password);
    const cErr = validateConfirm(confirmPassword);
    setNameError(nErr);
    setEmailError(eErr);
    setPasswordError(pErr);
    setConfirmError(cErr);
    if (nErr || eErr || pErr || cErr) return;

    setSubmitError("");
    setLoading(true);
    try {
      const raw = (i18n.language ?? "en").split("-")[0];
      const lang = ["en", "ar", "es", "zh", "ru", "fr"].includes(raw) ? raw : "en";
      await register(email, password, name, undefined, lang);
      navigate(returnPath, { replace: true });
    } catch (err: unknown) {
      const message =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : t("auth.registerError");
      setSubmitError(typeof message === "string" ? message : t("auth.registerError"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout>
      <form onSubmit={handleSubmit} className="space-y-6">
        <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">
          {t("auth.registerTitle")}
        </h1>

        {submitError && (
          <div className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive dark:bg-destructive/20 dark:text-destructive">
            {submitError}
          </div>
        )}

        <div className="space-y-2">
          <label htmlFor="name" className="text-sm font-medium">
            {t("auth.name")}
          </label>
          <div className="relative">
            <User className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground dark:text-muted-foreground" />
            <Input
              id="name"
              type="text"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setNameError("");
              }}
              onBlur={handleNameBlur}
              autoComplete="name"
              className={cn(
                "pl-9",
                nameError && "border-destructive focus-visible:ring-destructive"
              )}
            />
          </div>
          {nameError && (
            <p className="text-xs text-destructive dark:text-destructive">{nameError}</p>
          )}
        </div>

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
                setConfirmError(confirmPassword ? validateConfirm(confirmPassword) : "");
              }}
              onBlur={handlePasswordBlur}
              autoComplete="new-password"
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
          {password.length > 0 && (
            <div className="space-y-1">
              <Progress
                value={strengthPercent}
                max={100}
                variant={
                  passwordStrength === "strong"
                    ? "default"
                    : passwordStrength === "medium"
                      ? "warning"
                      : "danger"
                }
                className="h-1"
              />
              <p className="text-xs text-muted-foreground dark:text-muted-foreground">
                {t(strengthKey)}
              </p>
            </div>
          )}
          {passwordError && (
            <p className="text-xs text-destructive dark:text-destructive">{passwordError}</p>
          )}
        </div>

        <div className="space-y-2">
          <label htmlFor="confirmPassword" className="text-sm font-medium">
            {t("auth.confirmPassword")}
          </label>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground dark:text-muted-foreground" />
            <Input
              id="confirmPassword"
              type={showPassword ? "text" : "password"}
              value={confirmPassword}
              onChange={(e) => {
                setConfirmPassword(e.target.value);
                setConfirmError("");
              }}
              onBlur={handleConfirmBlur}
              autoComplete="new-password"
              className={cn(
                "pl-9",
                confirmError && "border-destructive focus-visible:ring-destructive"
              )}
            />
          </div>
          {confirmError && (
            <p className="text-xs text-destructive dark:text-destructive">{confirmError}</p>
          )}
        </div>

        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            t("auth.submitRegister")
          )}
        </Button>

        <p className="text-center text-sm text-muted-foreground dark:text-muted-foreground">
          {t("auth.hasAccount")}{" "}
          <Link
            to={location.search ? `/login${location.search}` : "/login"}
            className="font-medium text-primary hover:underline dark:text-primary"
          >
            {t("auth.login")}
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}
