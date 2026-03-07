/**
 * Force password change page for users with force_password_change=true.
 * Shown after first superuser login with default credentials.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Mail, Lock, Eye, EyeOff, Loader2 } from "lucide-react";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/api/client";
import { useAuthStore } from "@/stores/authStore";
import { cn } from "@/lib/utils";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function ForcePasswordChangePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const fetchUser = useAuthStore((s) => s.fetchUser);

  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [emailError, setEmailError] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [confirmError, setConfirmError] = useState("");
  const [submitError, setSubmitError] = useState("");
  const [loading, setLoading] = useState(false);

  const validateEmail = (value: string) => {
    if (!value.trim()) return t("auth.fieldRequired");
    if (!EMAIL_REGEX.test(value)) return t("auth.emailInvalid");
    return "";
  };

  const validatePassword = (value: string) => {
    if (!value) return t("auth.fieldRequired");
    if (value.length < 8) return t("forcePassword.passwordTooShort");
    return "";
  };

  const validateConfirm = (value: string) => {
    if (value !== newPassword) return t("forcePassword.passwordMismatch");
    return "";
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const eErr = validateEmail(newEmail);
    const pErr = validatePassword(newPassword);
    const cErr = validateConfirm(confirmPassword);
    setEmailError(eErr);
    setPasswordError(pErr);
    setConfirmError(cErr);
    if (eErr || pErr || cErr) return;

    setSubmitError("");
    setLoading(true);
    try {
      const { data } = await apiClient.post<{
        access_token: string;
        refresh_token: string;
        persistent?: boolean;
        expires_at?: string;
      }>("/auth/change-initial-password", {
        new_email: newEmail,
        new_password: newPassword,
      });
      useAuthStore.getState().setTokensFromResponse(data);
      await fetchUser();
      navigate("/dashboard", { replace: true });
    } catch (err: unknown) {
      const message =
        err &&
        typeof err === "object" &&
        "response" in err &&
        (err as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail;
      setSubmitError(
        typeof message === "string" ? message : t("common.error")
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout>
      <form onSubmit={handleSubmit} className="space-y-6">
        <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">
          {t("forcePassword.title")}
        </h1>
        <p className="text-muted-foreground">{t("forcePassword.subtitle")}</p>

        {submitError && (
          <div className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {submitError}
          </div>
        )}

        <div className="space-y-2">
          <label htmlFor="newEmail" className="text-sm font-medium">
            {t("forcePassword.newEmail")}
          </label>
          <div className="relative">
            <Mail className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="newEmail"
              type="email"
              placeholder={t("auth.emailPlaceholder")}
              value={newEmail}
              onChange={(e) => {
                setNewEmail(e.target.value);
                setEmailError("");
              }}
              onBlur={() => setEmailError(validateEmail(newEmail))}
              autoComplete="email"
              className={cn(
                "pl-9",
                emailError && "border-destructive focus-visible:ring-destructive"
              )}
            />
          </div>
          {emailError && (
            <p className="text-xs text-destructive">{emailError}</p>
          )}
        </div>

        <div className="space-y-2">
          <label htmlFor="newPassword" className="text-sm font-medium">
            {t("forcePassword.newPassword")}
          </label>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="newPassword"
              type={showPassword ? "text" : "password"}
              value={newPassword}
              onChange={(e) => {
                setNewPassword(e.target.value);
                setPasswordError("");
                setConfirmError(confirmPassword ? validateConfirm(confirmPassword) : "");
              }}
              onBlur={() => setPasswordError(validatePassword(newPassword))}
              autoComplete="new-password"
              className={cn(
                "pr-9 pl-9",
                passwordError && "border-destructive focus-visible:ring-destructive"
              )}
            />
            <button
              type="button"
              onClick={() => setShowPassword((s) => !s)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              aria-label={showPassword ? t("common.hidePassword") : t("common.showPassword")}
            >
              {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
          {passwordError && (
            <p className="text-xs text-destructive">{passwordError}</p>
          )}
        </div>

        <div className="space-y-2">
          <label htmlFor="confirmPassword" className="text-sm font-medium">
            {t("forcePassword.confirmPassword")}
          </label>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="confirmPassword"
              type={showPassword ? "text" : "password"}
              value={confirmPassword}
              onChange={(e) => {
                setConfirmPassword(e.target.value);
                setConfirmError("");
              }}
              onBlur={() => setConfirmError(validateConfirm(confirmPassword))}
              autoComplete="new-password"
              className={cn(
                "pl-9",
                confirmError && "border-destructive focus-visible:ring-destructive"
              )}
            />
          </div>
          {confirmError && (
            <p className="text-xs text-destructive">{confirmError}</p>
          )}
        </div>

        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            t("forcePassword.submit")
          )}
        </Button>
      </form>
    </AuthLayout>
  );
}
