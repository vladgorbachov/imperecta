import { useTranslation } from "react-i18next";

export function ProductsTable() {
  const { t } = useTranslation();
  return (
    <div className="rounded-lg border">
      <table className="w-full">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="min-w-[140px] p-4 text-left">{t("dashboard.product")}</th>
            <th className="min-w-[80px] p-4 text-left">{t("products.sku")}</th>
            <th className="min-w-[90px] p-4 text-left">{t("common.price")}</th>
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
