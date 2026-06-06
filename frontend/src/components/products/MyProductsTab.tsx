/**
 * Displays user's own products with CRUD.
 *
 * Toolbar:
 * - Search, category filter, sort
 * - Add product button (navigates to import flow)
 * - CSV import button (navigates to import)
 * - Excel import button (navigates to import, accepts .xls, .xlsx, .xlsm)
 *
 * Table: checkboxes, SKU, name, price columns, actions (edit, delete)
 * Bulk delete: select rows, Ctrl+A, Delete key, SelectionActionBar.
 */

import { useState, useCallback, useEffect } from "react";
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
import { PriceDisplay } from "@/components/ui-custom/PriceDisplay";
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
import { Checkbox } from "@/components/ui/checkbox";
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
import { useQueryClient } from "@tanstack/react-query";
import { productsApi } from "@/api/products";
import { useRowSelection } from "@/hooks/useRowSelection";
import { SelectionActionBar } from "./SelectionActionBar";
import { DeleteConfirmDialog } from "./DeleteConfirmDialog";
import { cn } from "@/lib/utils";

const PAGE_SIZES = [20, 50, 100] as const;
const SORT_OPTIONS = [
  { value: "recent", labelKey: "products.sort.recent" },
  { value: "name_asc", labelKey: "products.sort.nameAsc" },
  { value: "name_desc", labelKey: "products.sort.nameDesc" },
  { value: "price_asc", labelKey: "products.sort.priceAsc" },
  { value: "price_desc", labelKey: "products.sort.priceDesc" },
] as const;

export function MyProductsTab({ locale: _locale }: { locale: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { canAddProducts } = usePlanLimits();

  const [searchRaw, setSearchRaw] = useState("");
  const [category, setCategory] = useState<string>("all");
  const [sort, setSort] = useState<string>("recent");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

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

  const pageItemIds = products.map((p) => p.id);
  const {
    selectedIds,
    selectedCount,
    toggleItem,
    toggleAll,
    clearSelection,
    isAllSelected,
    isSelected,
  } = useRowSelection({ pageItemIds });

  useEffect(() => {
    clearSelection();
  }, [page, clearSelection]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Delete" && selectedCount > 0) {
        const tag = (e.target as HTMLElement)?.tagName;
        if (tag !== "INPUT" && tag !== "TEXTAREA") {
          e.preventDefault();
          setShowDeleteDialog(true);
        }
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [selectedCount]);

  const totalPages = Math.ceil(total / pageSize) || 1;
  const clampedPage = Math.min(page, totalPages) || 1;
  const start = (clampedPage - 1) * pageSize;
  const hasFilters = !!search || (!!category && category !== "all");
  const isEmpty = products.length === 0 && !isLoading;

  const handleBulkDelete = useCallback(async () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    setIsDeleting(true);
    try {
      const { data } = await productsApi.bulkDelete(ids);
      toast.success(t("products.bulkDeleted", { count: data.deleted }));
      clearSelection();
      setShowDeleteDialog(false);
      queryClient.invalidateQueries({ queryKey: ["products"] });
    } catch {
      toast.error(t("products.bulkDeleteFailed"));
    } finally {
      setIsDeleting(false);
    }
  }, [selectedIds, clearSelection, queryClient, t]);

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
      if (!confirm(t("products.deleteConfirm"))) return;
      deleteMutation.mutate(id, {
        onSuccess: () => toast.success(t("products.deleted")),
        onError: () => toast.error(t("products.deleteFailed")),
      });
    },
    [deleteMutation, t]
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
              placeholder={t("products.searchByNameOrSku")}
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
              <SelectValue placeholder={t("products.category")} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("products.allCategories")}</SelectItem>
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
              <SelectValue placeholder={t("products.sorting")} />
            </SelectTrigger>
            <SelectContent>
              {SORT_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {t(o.labelKey)}
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
            {t("products.importCsv")}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleImportExcel}
            disabled={!canAddProducts}
            title={!canAddProducts ? t("planLimit.cannotAdd") : undefined}
          >
            <FileSpreadsheet className="mr-2 size-4" />
            {t("products.importExcel")}
          </Button>
          <Button
            size="sm"
            onClick={handleAddProduct}
            disabled={!canAddProducts}
            title={!canAddProducts ? t("planLimit.cannotAdd") : undefined}
          >
            <Plus className="mr-2 size-4" />
            {t("products.addProduct")}
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
            <p className="text-sm text-muted-foreground">{t("products.noResults")}</p>
            <Button
              variant="outline"
              onClick={() => {
                setSearchRaw("");
                setCategory("all");
                setPage(1);
              }}
            >
              {t("products.clearFilters")}
            </Button>
          </div>
        ) : (
          <>
            <div className="max-h-[55vh] overflow-x-auto overflow-y-auto scrollbar-none sm:max-h-[calc(100vh-20rem)]">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="w-12">
                      <Checkbox
                        checked={isAllSelected}
                        onCheckedChange={toggleAll}
                        aria-label={t("products.selectAll")}
                      />
                    </TableHead>
                    <TableHead>SKU</TableHead>
                    <TableHead>{t("products.name")}</TableHead>
                    <TableHead>{t("products.myPrice")}</TableHead>
                    <TableHead>{t("products.minCompetitorPrice")}</TableHead>
                    <TableHead className="w-10" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {products.map((p) => (
                    <TableRow
                      key={p.id}
                      className={cn(
                        "cursor-pointer transition-colors",
                        isSelected(p.id)
                          ? "border-l-2 border-l-blue-500 bg-blue-500/10 hover:bg-blue-500/15"
                          : "hover:bg-muted/50"
                      )}
                      onClick={(e) => {
                        if (e.ctrlKey || e.metaKey) {
                          e.preventDefault();
                          toggleItem(p.id);
                        } else {
                          navigate(`/products/${p.id}`);
                        }
                      }}
                    >
                      <TableCell
                        className="w-12"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Checkbox
                          checked={isSelected(p.id)}
                          onCheckedChange={() => toggleItem(p.id)}
                          aria-label={t("products.selectProduct", { name: p.name })}
                        />
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {p.sku ?? "—"}
                      </TableCell>
                      <TableCell>
                        <span className="font-medium">{p.name}</span>
                      </TableCell>
                      <TableCell>
                        <PriceDisplay
                          localAmount={p.current_price}
                          localCurrency={p.currency}
                          displayAmount={p.display_price}
                          displayCurrency={p.display_currency}
                          conversionAvailable={p.conversion_available}
                        />
                      </TableCell>
                      <TableCell>
                        <PriceDisplay
                          localAmount={p.min_competitor_price}
                          localCurrency={p.currency}
                          displayAmount={p.min_competitor_display_price}
                          displayCurrency={p.display_currency}
                          conversionAvailable={p.conversion_available}
                        />
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
                              {t("common.edit")}
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              className="text-destructive"
                              onClick={(e) => handleDelete(p.id, e as unknown as React.MouseEvent)}
                            >
                              <Trash2 className="mr-2 size-4" />
                              {t("common.delete")}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            {selectedCount > 0 && (
              <SelectionActionBar
                selectedCount={selectedCount}
                onDelete={() => setShowDeleteDialog(true)}
                onClear={clearSelection}
                isDeleting={isDeleting}
              />
            )}
          </>
        )}
      </div>

      <DeleteConfirmDialog
        open={showDeleteDialog}
        onCancel={() => setShowDeleteDialog(false)}
        onConfirm={handleBulkDelete}
        count={selectedCount}
        isLoading={isDeleting}
      />

      {/* Pagination */}
      {!isEmpty && !isLoading && total > 0 && (
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-muted-foreground">
            {t("products.paginationShown", {
              from: start + 1,
              to: Math.min(start + pageSize, total),
              total,
            })}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={clampedPage <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              {t("common.back")}
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
              {t("common.next")}
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
