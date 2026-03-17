import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

export function NotFoundPage() {
  const { t } = useTranslation();

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 p-4">
      <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">
        {t("common.notFound")}
      </h1>
      <Button asChild>
        <Link to="/dashboard">{t("common.backToMarkets")}</Link>
      </Button>
    </div>
  );
}
