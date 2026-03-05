import { useTranslation } from "react-i18next";

export function CompetitorPricesTable() {
  const { t } = useTranslation();
  return (
    <div className="rounded-lg border">
      <table className="w-full">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="min-w-[120px] p-4 text-left">{t("dashboard.competitor")}</th>
            <th className="min-w-[90px] p-4 text-left">{t("common.price")}</th>
            <th className="min-w-[80px] p-4 text-left">{t("common.status")}</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td colSpan={3} className="p-8 text-center text-muted-foreground">
              {t("common.noData")}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
