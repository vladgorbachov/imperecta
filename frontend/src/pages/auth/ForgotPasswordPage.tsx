import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { Button } from "@/components/ui/button";

export function ForgotPasswordPage() {
  const { t } = useTranslation();

  return (
    <AuthLayout>
      <div className="space-y-6 text-center">
        <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">
          {t("auth.forgotPasswordTitle")}
        </h1>
        <p className="text-muted-foreground dark:text-muted-foreground">
          {t("auth.forgotPasswordComingSoon")}
        </p>
        <Button asChild className="w-full">
          <Link to="/login">{t("auth.login")}</Link>
        </Button>
      </div>
    </AuthLayout>
  );
}
