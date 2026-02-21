import { ProductsTable } from "../components/tables/ProductsTable";

export function ProductsPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Товары</h2>
      <ProductsTable />
    </div>
  );
}
