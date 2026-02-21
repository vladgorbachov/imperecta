import { PriceChart } from "../components/charts/PriceChart";

export function DashboardPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Дашборд</h2>
      <PriceChart />
    </div>
  );
}
