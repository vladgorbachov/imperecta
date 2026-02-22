import { useTranslation } from "react-i18next";
import { useDashboardSummary } from "@/hooks/useAnalytics";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";

export function DashboardPage() {
  const { t } = useTranslation();
  const { data, isLoading } = useDashboardSummary();

  const priceChangesTotal =
    data?.price_changes_today != null
      ? (data.price_changes_today.drops ?? 0) + (data.price_changes_today.increases ?? 0)
      : 0;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">{t("nav.dashboard")}</h1>

      {/* Stat cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <Skeleton className="h-4 w-24" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-16" />
              </CardContent>
            </Card>
          ))
        ) : (
          <>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {t("dashboard.products")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{data?.total_products ?? 0}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {t("dashboard.competitors")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{data?.total_competitors ?? 0}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {t("dashboard.alertsToday")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {data?.alerts_triggered_today ?? 0}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {t("dashboard.priceChanges")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{priceChangesTotal}</div>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      {/* Top 5 changes */}
      <Card>
        <CardHeader>
          <CardTitle>{t("dashboard.topChanges")}</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : !data?.top_changes?.length ? (
            <p className="text-sm text-muted-foreground">{t("dashboard.noData")}</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("dashboard.product")}</TableHead>
                  <TableHead>{t("dashboard.competitor")}</TableHead>
                  <TableHead>{t("dashboard.was")}</TableHead>
                  <TableHead>{t("dashboard.became")}</TableHead>
                  <TableHead>{t("dashboard.change")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.top_changes.map((row, i) => {
                  const isDrop = row.change_percent < 0;
                  return (
                    <TableRow key={i}>
                      <TableCell className="font-medium">{row.product_name}</TableCell>
                      <TableCell>{row.competitor_name}</TableCell>
                      <TableCell>{Number(row.old_price).toFixed(2)} ₽</TableCell>
                      <TableCell>{Number(row.new_price).toFixed(2)} ₽</TableCell>
                      <TableCell>
                        <span
                          className={
                            isDrop
                              ? "font-medium text-green-600"
                              : "font-medium text-red-600"
                          }
                        >
                          {row.change_percent > 0 ? "+" : ""}
                          {row.change_percent.toFixed(1)}%
                        </span>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Active promos */}
      <Card>
        <CardHeader>
          <CardTitle>{t("dashboard.activePromos")}</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex flex-wrap gap-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-6 w-24" />
              ))}
            </div>
          ) : !data?.active_promos?.length ? (
            <p className="text-sm text-muted-foreground">{t("dashboard.noData")}</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {data.active_promos.map((p, i) => (
                <Badge key={i} variant="secondary" className="text-xs">
                  {p.competitor_name}: {p.promo_label}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
