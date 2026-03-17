/**
 * Displays user's own products with CRUD.
 *
 * Toolbar:
 * - Search, category filter, sort
 * - "+ Добавить товар" button (navigates to add flow)
 * - "Импорт CSV" button (navigates to import)
 * - "Импорт Excel" button (navigates to import, accepts .xls, .xlsx, .xlsm)
 *
 * Table: SKU, name, "Моя цена", "Мин. цена конкурентов", actions (edit, delete)
 */

import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Plus,
  Upload,
  FileSpreadsheet,
  Search,
  MoreHorizontal,
  Pencil,
  Trash2,
} from "lucide-react";
import { formatPrice } from "@/lib/formatters";
import { useDebounce } from "@/hooks/useDebounce";
import { useProducts, useProductCategories } from "@/hooks/useProducts";
import { usePlanLimits } from "@/hooks/usePlanLimits";
import { PlanLimitBanner } from "@/components/ui-custom/PlanLimitBanner";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { Package } from "lucide-react";
import { toast } from "sonner";
import { IMPORT_ACCEPT } from "@/api/import";

const PAGE_SIZES = [20, 50, 100] as const;
const SORT_OPTIONS = [
  { value: "recent", label: "По дате" },
  { value: "name_asc", label: "По алфавиту ↑" },
  { value: "name_desc", label: "По алфавиту ↓" },
  { value: "price_asc", label: "По цене ↑" },
  { value: "price_desc", label: "По цене ↓" },
] as const;

export function MyProductsTab({ locale }: { locale: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { canAddProducts } = usePlanLimits();

  const [searchRaw, setSearchRaw] = useState("");
  const [category, setCategory] = useState<string>("all");
  const [sort, setSort] = useState<string>("recent");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const search = useDebounce(searchRaw, 500);
  const categoryParam = category && category !== "all" ? category : undefined;

  const { products, total, isLoading, deleteMutation } = useProducts({
    search: search || undefined,
    category: categoryParam,
    sort,
    page,
    limit: pageSize,
  });
  const { data: categories = [] } = useProductCategories();

  const totalPages = Math.ceil(total / pageSize) || 1;
  const clampedPage = Math.min(page, totalPages) || 1;
  const start = (clampedPage - 1) * pageSize;
  const hasFilters = !!search || (!!category && category !== "all");
  const isEmpty = products.length === 0 && !isLoading;

  const handleAddProduct = useCallback(() => {
    navigate("/import");
  }, [navigate]);

  const handleImportCsv = useCallback(() => {
    navigate("/import");
  }, [navigate]);

  const handleImportExcel = useCallback(() => {
    navigate("/import");
  }, [navigate]);

  const handleDelete = useCallback(
    (id: string, e: React.MouseEvent) => {
      e.stopPropagation();
      if (!confirm("Удалить товар?")) return;
      deleteMutation.mutate(id, {
        onSuccess: () => toast.success("Товар удалён"),
        onError: () => toast.error("Ошибка удаления"),
      });
    },
    [deleteMutation]
  );

  return (
    <div className="flex flex-col gap-4">
      <PlanLimitBanner className="mb-0" />
      {/* Toolbar */}
      <div className="glass-card flex flex-col gap-4 rounded-xl p-4 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
        <div className="flex w-full flex-col gap-4 sm:flex-row sm:items-center sm:gap-2 lg:w-auto">
          <div className="relative flex-1 lg:max-w-72">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Поиск по названию или SKU"
              value={searchRaw}
              onChange={(e) => {
                setSearchRaw(e.target.value);
                setPage(1);
              }}
              className="w-full pl-9"
            />
          </div>
          <Select
            value={category}
            onValueChange={(v) => {
              setCategory(v);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-full sm:w-48">
              <SelectValue placeholder="Категория" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Все категории</SelectItem>
              {categories.map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={sort}
            onValueChange={(v) => {
              setSort(v);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-full sm:w-48">
              <SelectValue placeholder="Сортировка" />
            </SelectTrigger>
            <SelectContent>
              {SORT_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleImportCsv}
            disabled={!canAddProducts}
            title={!canAddProducts ? t("planLimit.cannotAdd") : undefined}
          >
            <Upload className="mr-2 size-4" />
            Импорт CSV
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleImportExcel}
            disabled={!canAddProducts}
            title={!canAddProducts ? t("planLimit.cannotAdd") : undefined}
          >
            <FileSpreadsheet className="mr-2 size-4" />
            Импорт Excel
          </Button>
          <Button
            size="sm"
            onClick={handleAddProduct}
            disabled={!canAddProducts}
            title={!canAddProducts ? t("planLimit.cannotAdd") : undefined}
          >
            <Plus className="mr-2 size-4" />
            Добавить товар
          </Button>
        </div>
      </div>

      {/* Table */}
      <div className="glass-card overflow-hidden rounded-xl">
        {isLoading ? (
          <div className="p-4">
            <div className="space-y-2">
              {Array.from({ length: 7 }).map((_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          </div>
        ) : isEmpty && !hasFilters ? (
          <EmptyState
            title="products.noProducts"
            description="products.noProductsHint"
            icon={Package}
            action={
              canAddProducts
                ? { label: "products.addProduct", onClick: handleAddProduct }
                : undefined
            }
          />
        ) : isEmpty && hasFilters ? (
          <div className="flex flex-col items-center justify-center gap-4 px-4 py-12">
            <p className="text-sm text-muted-foreground">Нет результатов</p>
            <Button
              variant="outline"
              onClick={() => {
                setSearchRaw("");
                setCategory("all");
                setPage(1);
              }}
            >
              Сбросить фильтры
            </Button>
          </div>
        ) : (
          <div className="max-h-[55vh] overflow-x-auto overflow-y-auto scrollbar-none sm:max-h-[calc(100vh-20rem)]">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>SKU</TableHead>
                  <TableHead>Название</TableHead>
                  <TableHead>Моя цена</TableHead>
                  <TableHead>Мин. цена конкурентов</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {products.map((p) => (
                  <TableRow
                    key={p.id}
                    className="cursor-pointer transition-colors hover:bg-muted/50"
                    onClick={() => navigate(`/products/${p.id}`)}
                  >
                    <TableCell className="text-muted-foreground">
                      {p.sku ?? "—"}
                    </TableCell>
                    <TableCell>
                      <span className="font-medium">{p.name}</span>
                    </TableCell>
                    <TableCell>
                      {formatPrice(p.current_price, p.currency, locale)}
                    </TableCell>
                    <TableCell>
                      {p.min_competitor_price != null
                        ? formatPrice(p.min_competitor_price, p.currency, locale)
                        : "—"}
                    </TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="size-8">
                            <MoreHorizontal className="size-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => navigate(`/products/${p.id}`)}>
                            <Pencil className="mr-2 size-4" />
                            Редактировать
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            className="text-destructive"
                            onClick={(e) => handleDelete(p.id, e as unknown as React.MouseEvent)}
                          >
                            <Trash2 className="mr-2 size-4" />
                            Удалить
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

      {/* Pagination */}
      {!isEmpty && !isLoading && total > 0 && (
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-muted-foreground">
            Показано {start + 1}–{Math.min(start + pageSize, total)} из {total}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={clampedPage <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Назад
            </Button>
            <span className="px-2 text-sm">
              {clampedPage} / {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={clampedPage >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              Вперёд
            </Button>
            <Select
              value={String(pageSize)}
              onValueChange={(v) => {
                setPageSize(Number(v));
                setPage(1);
              }}
            >
              <SelectTrigger className="h-9 w-20">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PAGE_SIZES.map((s) => (
                  <SelectItem key={s} value={String(s)}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      )}
    </div>
  );
}
