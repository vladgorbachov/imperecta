import { useParams } from "react-router-dom";
import { PriceChart } from "../components/charts/PriceChart";
import { CompetitorPricesTable } from "../components/tables/CompetitorPricesTable";

export function ProductDetailPage() {
  const { id } = useParams();
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Товар {id}</h2>
      <PriceChart />
      <CompetitorPricesTable />
    </div>
  );
}
