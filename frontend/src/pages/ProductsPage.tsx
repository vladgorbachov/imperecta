import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Plus, Upload } from "lucide-react";
import { format } from "date-fns";
import { useProducts, useProductCategories } from "@/hooks/useProducts";
import { useQueryClient } from "@tanstack/react-query";
import { importApi } from "@/api/import";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import type { ProductListItem } from "@/api/products";

const PAGE_SIZE = 20;

export function ProductsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string>("");
  const [page, setPage] = useState(1);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [addForm, setAddForm] = useState({
    name: "",
    sku: "",
    current_price: "",
    category: "",
    url: "",
  });
  const [importing, setImporting] = useState(false);

  const { products, total, isLoading, createMutation } = useProducts({
    search: search || undefined,
    category: category || undefined,
    page,
    limit: PAGE_SIZE,
  });
  const { data: categories } = useProductCategories();

  const totalPages = Math.ceil(total / PAGE_SIZE) || 1;

  const handleAddProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    const price = parseFloat(addForm.current_price);
    if (!addForm.name || isNaN(price) || price < 0) {
      toast.error("Заполните название и цену");
      return;
    }
    try {
      await createMutation.mutateAsync({
        name: addForm.name,
        sku: addForm.sku || undefined,
        current_price: price,
        category: addForm.category || undefined,
        url: addForm.url || undefined,
      });
      toast.success("Товар добавлен");
      setAddDialogOpen(false);
      setAddForm({ name: "", sku: "", current_price: "", category: "", url: "" });
    } catch {
      toast.error("Ошибка при добавлении");
    }
  };

  const handleImportCsv = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    try {
      const { data } = await importApi.uploadProductsCsv(file);
      queryClient.invalidateQueries({ queryKey: ["products"] });
      toast.success(`Импортировано: ${data.imported}`);
      if (data.errors?.length) {
        toast.error(`Ошибки: ${data.errors.length}`);
      }
    } catch {
      toast.error("Ошибка импорта");
    } finally {
      setImporting(false);
      e.target.value = "";
    }
  };

  return (
    <div className="space-y-6 text-neutral-900">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-bold text-neutral-900">{t("nav.products")}</h1>
        <div className="flex gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={handleImportCsv}
            disabled={importing}
          />
          <Button
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
            disabled={importing}
          >
            <Upload className="mr-2 size-4" />
            {t("products.importCsv")}
          </Button>
          <Button onClick={() => setAddDialogOpen(true)}>
            <Plus className="mr-2 size-4" />
            {t("products.addProduct")}
          </Button>
        </div>
      </div>

      <div className="flex flex-col gap-4 sm:flex-row">
        <Input
          placeholder={t("products.search")}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="max-w-sm"
        />
        <Select
          value={category}
          onValueChange={(v) => {
            setCategory(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder={t("products.category")} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">{t("products.allCategories")}</SelectItem>
            {categories?.map((c) => (
              <SelectItem key={c} value={c}>
                {c}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="rounded-md border">
        {isLoading ? (
          <div className="p-4 space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("products.name")}</TableHead>
                <TableHead>{t("products.sku")}</TableHead>
                <TableHead>{t("products.myPrice")}</TableHead>
                <TableHead>{t("products.minCompetitorPrice")}</TableHead>
                <TableHead>{t("products.maxPrice")}</TableHead>
                <TableHead>{t("products.competitorCount")}</TableHead>
                <TableHead>{t("products.lastParsing")}</TableHead>
                <TableHead className="w-24" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {products.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-center text-muted-foreground">
                    {t("dashboard.noData")}
                  </TableCell>
                </TableRow>
              ) : (
                products.map((p) => (
                  <ProductRow key={p.id} product={p} onRowClick={() => navigate(`/products/${p.id}`)} />
                ))
              )}
            </TableBody>
          </Table>
        )}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {total} {t("dashboard.products").toLowerCase()}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              Назад
            </Button>
            <span className="flex items-center px-2 text-sm">
              {page} / {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Вперёд
            </Button>
          </div>
        </div>
      )}

      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("products.addProduct")}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleAddProduct}>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">{t("products.name")} *</label>
                <Input
                  value={addForm.name}
                  onChange={(e) => setAddForm((f) => ({ ...f, name: e.target.value }))}
                  required
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">{t("products.sku")}</label>
                <Input
                  value={addForm.sku}
                  onChange={(e) => setAddForm((f) => ({ ...f, sku: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">{t("products.myPrice")} *</label>
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={addForm.current_price}
                  onChange={(e) =>
                    setAddForm((f) => ({ ...f, current_price: e.target.value }))
                  }
                  required
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">{t("products.category")}</label>
                <Input
                  value={addForm.category}
                  onChange={(e) =>
                    setAddForm((f) => ({ ...f, category: e.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">URL</label>
                <Input
                  type="url"
                  placeholder="https://..."
                  value={addForm.url}
                  onChange={(e) =>
                    setAddForm((f) => ({ ...f, url: e.target.value }))
                  }
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setAddDialogOpen(false)}
              >
                Отмена
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                Добавить
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function ProductRow({
  product,
  onRowClick,
}: {
  product: ProductListItem;
  onRowClick: () => void;
}) {
  const { t } = useTranslation();
  const minPrice = product.min_competitor_price;
  const myPrice = product.current_price;
  const isOverpriced = minPrice != null && myPrice > minPrice;

  return (
    <TableRow
      className="cursor-pointer hover:bg-muted/50"
      onClick={onRowClick}
    >
      <TableCell className="font-medium">{product.name}</TableCell>
      <TableCell>{product.sku ?? "—"}</TableCell>
      <TableCell>{Number(product.current_price).toFixed(2)} ₽</TableCell>
      <TableCell>
        {minPrice != null ? (
          <span className={isOverpriced ? "text-red-600 font-medium" : ""}>
            {Number(minPrice).toFixed(2)} ₽
          </span>
        ) : (
          "—"
        )}
      </TableCell>
      <TableCell>
        {product.max_competitor_price != null
          ? `${Number(product.max_competitor_price).toFixed(2)} ₽`
          : "—"}
      </TableCell>
      <TableCell>{product.competitor_count}</TableCell>
      <TableCell>
        {product.last_checked_at
          ? format(new Date(product.last_checked_at), "dd.MM.yyyy HH:mm")
          : "—"}
      </TableCell>
      <TableCell>
        {isOverpriced ? (
          <Badge variant="destructive" className="text-xs">
            {t("products.overpriced")}
          </Badge>
        ) : (
          "—"
        )}
      </TableCell>
    </TableRow>
  );
}
