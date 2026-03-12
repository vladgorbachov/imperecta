// MOBILE-2026: fully responsive + bottom nav + drawer

/**
 * Competitors page: card grid (default) / table view, AI scoring, ComparisonMatrix.
 * i18n: nav.competitors, competitors.*, common.*
 */

import { useState, useRef, useEffect } from "react";
import { useTranslation } from "react-i18next";
import {
  Plus,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Users,
  Wand2,
  Search,
  LayoutGrid,
  Table as TableIcon,
  BarChart3,
  Sparkles,
  ChevronDown as ChevronDownIcon,
} from "lucide-react";
import { toast } from "sonner";
import { formatDate, formatPrice } from "@/lib/formatters";
import { useDebounce } from "@/hooks/useDebounce";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { competitorsApi } from "@/api/competitors";
import { analyticsApi } from "@/api/analytics";
import { productsApi } from "@/api/products";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
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
import { MarketplaceBadge } from "@/components/ui-custom/MarketplaceBadge";
import { SearchableMarketplaceSelect } from "@/components/ui-custom/SearchableMarketplaceSelect";
import type { MarketplaceId } from "@/components/ui-custom/SearchableMarketplaceSelect";
import { TrendBadge } from "@/components/ui-custom/TrendBadge";
import { CircularScore } from "@/components/ui-custom/CircularScore";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { PageHeader } from "@/components/ui-custom/PageHeader";
import { PriceSparkline } from "@/components/competitors/PriceSparkline";
import { ComparisonMatrix } from "@/components/competitors/ComparisonMatrix";
import { cn } from "@/lib/utils";
import type { Competitor, CompetitorProduct } from "@/api/competitors";

type Marketplace = "ozon" | "wildberries" | "kaspi";
type ScraperType = "auto" | "ozon_api" | "wb_api" | "css_selector" | "json_api";
type ViewMode = "grid" | "table";

function mapScraperToApi(type: ScraperType): string {
  switch (type) {
    case "auto": return "auto";
    case "ozon_api": return "ozon";
    case "wb_api": return "wildberries";
    case "css_selector": return "generic";
    case "json_api": return "generic";
    default: return "auto";
  }
}

function getScraperLabel(type: ScraperType): string {
  switch (type) {
    case "auto": return "competitors.scraperAuto";
    case "ozon_api": return "competitors.scraperOzonApi";
    case "wb_api": return "competitors.scraperWbApi";
    case "css_selector": return "competitors.scraperCss";
    case "json_api": return "competitors.scraperJsonApi";
  }
}

function detectScraperFromUrl(url: string): ScraperType {
  const lower = url.toLowerCase();
  if (lower.includes("ozon.ru") || lower.includes("ozon.")) return "ozon_api";
  if (lower.includes("wildberries") || lower.includes("wb.ru")) return "wb_api";
  return "auto";
}

function strengthFromScore(score: number): "weak" | "moderate" | "strong" {
  if (score >= 70) return "strong";
  if (score >= 40) return "moderate";
  return "weak";
}

interface SearchableProductSelectProps {
  value: string;
  onChange: (value: string) => void;
  products: { id: string; name: string; sku: string | null }[];
  placeholder?: string;
}

function SearchableProductSelect({
  value,
  onChange,
  products,
  placeholder,
}: SearchableProductSelectProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  const filtered = products.filter(
    (p) =>
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      (p.sku?.toLowerCase().includes(search.toLowerCase()) ?? false)
  );

  const selectedProduct = products.find((p) => p.id === value);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div ref={ref} className="relative">
      <div
        className="flex h-10 w-full cursor-pointer items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2"
        onClick={() => setOpen(!open)}
      >
        <span className={selectedProduct ? "" : "text-muted-foreground"}>
          {selectedProduct
            ? `${selectedProduct.name}${selectedProduct.sku ? ` (${selectedProduct.sku})` : ""}`
            : placeholder ?? t("competitors.selectProduct")}
        </span>
      </div>
      {open && (
        <div className="absolute top-full left-0 right-0 z-50 mt-1 max-h-60 overflow-hidden rounded-md border border-border bg-popover shadow-md dark:border-border dark:bg-popover">
          <Input
            placeholder={t("products.search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="m-2 h-8"
            autoFocus
          />
          <div className="max-h-44 overflow-y-auto p-1">
            {filtered.map((p) => (
              <button
                key={p.id}
                type="button"
                className="flex w-full cursor-pointer items-center rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent hover:text-accent-foreground"
                onClick={() => {
                  onChange(p.id);
                  setOpen(false);
                  setSearch("");
                }}
              >
                {p.name}
                {p.sku && (
                  <span className="ml-2 text-muted-foreground">({p.sku})</span>
                )}
              </button>
            ))}
            {filtered.length === 0 && (
              <p className="px-2 py-4 text-center text-sm text-muted-foreground">
                {t("products.noResults")}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function CompetitorsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [searchRaw, setSearchRaw] = useState("");
  const [comparisonOpen, setComparisonOpen] = useState(false);
  const [addCompetitorOpen, setAddCompetitorOpen] = useState(false);
  const [addProductOpen, setAddProductOpen] = useState(false);
  const [selectedCompetitor, setSelectedCompetitor] = useState<Competitor | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [competitorForm, setCompetitorForm] = useState({
    name: "",
    website_url: "",
    marketplace: "" as MarketplaceId | "",
  });
  const [productForm, setProductForm] = useState({
    product_id: "",
    url: "",
    scraper_type: "auto" as ScraperType,
  });

  const search = useDebounce(searchRaw, 300);

  const { data: competitors = [], isLoading } = useQuery({
    queryKey: ["competitors"],
    queryFn: async () => {
      const { data } = await competitorsApi.list();
      return data;
    },
  });

  const { data: benchmarksRaw = [] } = useQuery({
    queryKey: ["analytics", "competitor-benchmark"],
    queryFn: () => analyticsApi.getCompetitorBenchmark().then((r) => r.data),
  });
  const benchmarkMap = Object.fromEntries(
    benchmarksRaw.map((b: { competitor_id?: string; competitor_name?: string; score?: number; trend_30d?: number[] }) => [
      (b as { competitor_id?: string }).competitor_id ?? "",
      {
        score: (b as { score?: number }).score ?? 0,
        trend_30d: (b as { trend_30d?: number[] }).trend_30d ?? [],
      },
    ])
  );

  const { data: productsData } = useQuery({
    queryKey: ["products"],
    queryFn: async () => {
      const { data } = await productsApi.list({ limit: 500 });
      return data;
    },
  });
  const products = productsData?.items ?? [];

  const filteredCompetitors = competitors.filter((c) =>
    search ? c.name.toLowerCase().includes(search.toLowerCase()) : true
  );

  const createMutation = useMutation({
    mutationFn: competitorsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["competitors"] });
      setAddCompetitorOpen(false);
      setCompetitorForm({ name: "", website_url: "", marketplace: "" });
      toast.success(t("competitors.addSuccess"));
    },
    onError: () => toast.error(t("competitors.addError")),
  });

  const addProductMutation = useMutation({
    mutationFn: (data: Parameters<typeof competitorsApi.addProduct>[0]) =>
      competitorsApi.addProduct({
        ...data,
        scraper_type: mapScraperToApi((data.scraper_type ?? "auto") as ScraperType),
      }),
    onSuccess: () => {
      if (selectedCompetitor) {
        queryClient.invalidateQueries({
          queryKey: ["competitors", selectedCompetitor.id, "products"],
        });
        queryClient.invalidateQueries({ queryKey: ["competitors"] });
      }
      setAddProductOpen(false);
      setProductForm({ product_id: "", url: "", scraper_type: "auto" });
      setSelectedCompetitor(null);
      toast.success(t("competitors.linkSuccess"));
    },
    onError: () => toast.error(t("competitors.linkError")),
  });

  const handleAddCompetitor = (e: React.FormEvent) => {
    e.preventDefault();
    if (!competitorForm.marketplace) {
      toast.error(t("common.error"));
      return;
    }
    const url = competitorForm.website_url.trim();
    if (url && !/^https?:\/\/.+/.test(url)) {
      toast.error(t("common.error"));
      return;
    }
    createMutation.mutate({
      name: competitorForm.name,
      website_url: url || undefined,
      marketplace: competitorForm.marketplace,
    });
  };

  const handleAddProduct = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCompetitor || !productForm.product_id) return;
    const scraperType = productForm.scraper_type;
    if (!scraperType) return;
    addProductMutation.mutate({
      product_id: productForm.product_id,
      competitor_id: selectedCompetitor.id,
      url: productForm.url,
      scraper_type: scraperType as ScraperType,
    });
  };

  const handleAutoDetect = () => {
    const detected = detectScraperFromUrl(productForm.url);
    setProductForm((f) => ({ ...f, scraper_type: detected }));
  };

  const handleWhatIsDoingNow = () => {
    toast.info(t("competitors.aiAnalyzing"));
    // TODO: POST /api/ai/competitor-analysis
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="nav.competitors"
        actions={
          <Button onClick={() => setAddCompetitorOpen(true)}>
            <Plus className="mr-2 size-4" />
            {t("competitors.addCompetitor")}
          </Button>
        }
      />

      {/* Toolbar */}
      <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
        <div className="flex w-full flex-col gap-4 sm:flex-row sm:items-center sm:gap-2">
          <div className="relative flex-1 sm:max-w-64">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder={t("products.search")}
              value={searchRaw}
              onChange={(e) => setSearchRaw(e.target.value)}
              className="w-full pl-9"
            />
          </div>
          <div className="flex rounded-md border border-input bg-background p-0.5">
            <Button
              variant={viewMode === "grid" ? "secondary" : "ghost"}
              size="sm"
              onClick={() => setViewMode("grid")}
              aria-label={t("competitors.viewGrid")}
            >
              <LayoutGrid className="size-4" />
            </Button>
            <Button
              variant={viewMode === "table" ? "secondary" : "ghost"}
              size="sm"
              onClick={() => setViewMode("table")}
              aria-label={t("competitors.viewTable")}
            >
              <TableIcon className="size-4" />
            </Button>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setComparisonOpen(true)}
          >
            <BarChart3 className="mr-2 size-4" />
            {t("competitors.compareAll")}
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-14 animate-pulse rounded-lg border bg-muted" />
          ))}
        </div>
      ) : competitors.length === 0 ? (
        <EmptyState
          title="competitors.noCompetitors"
          description="competitors.addCompetitor"
          icon={Users}
          action={{
            label: "competitors.addCompetitor",
            onClick: () => setAddCompetitorOpen(true),
          }}
        />
      ) : viewMode === "grid" ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4 lg:grid-cols-3">
          {filteredCompetitors.map((c) => (
            <CompetitorCard
              key={c.id}
              competitor={c}
              benchmark={benchmarkMap[c.id]}
              onWhatIsDoingNow={() => handleWhatIsDoingNow(c)}
              onDetails={() => setExpandedId((id) => (id === c.id ? null : c.id))}
              expanded={expandedId === c.id}
              products={products}
              onAddProduct={() => {
                setSelectedCompetitor(c);
                setAddProductOpen(true);
              }}
            />
          ))}
        </div>
      ) : (
        <div className="overflow-x-auto overflow-hidden rounded-lg border border-border dark:border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10" />
                <TableHead>{t("competitors.name")}</TableHead>
                <TableHead>{t("competitors.marketplace")}</TableHead>
                <TableHead>{t("competitors.score")}</TableHead>
                <TableHead>{t("competitors.aggressiveness")}</TableHead>
                <TableHead>{t("competitors.productsCountHeader")}</TableHead>
                <TableHead>{t("competitors.added")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredCompetitors.map((c) => (
                <ExpandableCompetitorRow
                  key={c.id}
                  competitor={c}
                  benchmark={benchmarkMap[c.id]}
                  products={products}
                  expanded={expandedId === c.id}
                  onToggle={() => setExpandedId((id) => (id === c.id ? null : c.id))}
                  onAddProduct={() => {
                    setSelectedCompetitor(c);
                    setAddProductOpen(true);
                  }}
                />
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <ComparisonMatrix
        open={comparisonOpen}
        onOpenChange={setComparisonOpen}
        products={products.map((p) => ({ id: p.id, name: p.name }))}
        competitors={competitors.map((c) => ({ id: c.id, name: c.name }))}
      />

      <AddCompetitorDialog
        open={addCompetitorOpen}
        onOpenChange={setAddCompetitorOpen}
        form={competitorForm}
        setForm={setCompetitorForm}
        onSubmit={handleAddCompetitor}
        isLoading={createMutation.isPending}
      />

      <AddCompetitorProductDialog
        open={addProductOpen}
        onOpenChange={(open) => {
          setAddProductOpen(open);
          if (!open) setSelectedCompetitor(null);
        }}
        competitorName={selectedCompetitor?.name ?? ""}
        form={productForm}
        setForm={setProductForm}
        products={products}
        onSubmit={handleAddProduct}
        onAutoDetect={handleAutoDetect}
        isLoading={addProductMutation.isPending}
      />
    </div>
  );
}

function CompetitorCard({
  competitor,
  onWhatIsDoingNow,
  onDetails,
  expanded,
  products,
  onAddProduct,
}: {
  competitor: Competitor;
  benchmark?: { score: number; trend_30d: number[] };
  onWhatIsDoingNow: () => void;
  onDetails: () => void;
  expanded: boolean;
  products: { id: string; name: string; sku: string | null }[];
  onAddProduct: () => void;
}) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  const marketplace = competitor.marketplace as Marketplace;
  const score = benchmark?.score ?? 0;
  const strength = strengthFromScore(score);
  const sparklineData = benchmark?.trend_30d ?? [];

  const { data: competitorProducts = [], isLoading } = useQuery({
    queryKey: ["competitors", competitor.id, "products"],
    queryFn: async () => {
      const { data } = await competitorsApi.getProducts(competitor.id);
      return data;
    },
    enabled: expanded,
  });

  const strengthKey =
    strength === "strong"
      ? "competitors.strengthStrong"
      : strength === "moderate"
        ? "competitors.strengthModerate"
        : "competitors.strengthWeak";

  return (
    <div className="flex flex-col rounded-lg border border-border bg-card p-4 shadow-sm dark:border-border dark:bg-card">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <a
            href={competitor.website_url ?? "#"}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-medium text-primary hover:underline dark:text-primary"
            onClick={(e) => e.stopPropagation()}
          >
            {competitor.name}
            <ExternalLink className="size-4 shrink-0" />
          </a>
          <div className="mt-1">
            <MarketplaceBadge marketplace={marketplace} size="sm" />
          </div>
        </div>
        <CircularScore value={score} size={44} strokeWidth={3} />
      </div>

      <div className="mt-3 h-10">
        <PriceSparkline data={sparklineData} />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span
          className={cn(
            "rounded-md border px-2 py-0.5 text-xs font-medium",
            strength === "strong" &&
              "bg-[var(--color-price-up-bg)] text-[var(--color-price-up)] border-[var(--color-price-up-border)]",
            strength === "moderate" &&
              "bg-[var(--color-promo-bg)] text-[var(--color-promo)] border-[var(--color-promo-border)]",
            strength === "weak" &&
              "bg-[var(--color-muted-bg)] text-[var(--foreground-muted)] border-[var(--glass-border)]"
          )}
        >
          {t(strengthKey)}
        </span>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          variant="outline"
          size="sm"
          className="flex-1"
          onClick={onWhatIsDoingNow}
        >
          <Sparkles className="mr-2 size-4" />
          {t("competitors.whatIsDoingNow")}
        </Button>
        <Button variant="outline" size="sm" onClick={onDetails}>
          <ChevronDownIcon
            className={cn("mr-2 size-4 transition-transform", expanded && "rotate-180")}
          />
          {t("competitors.details")}
        </Button>
      </div>

      {expanded && (
        <div className="mt-4 border-t border-border pt-4 dark:border-border">
          <div className="mb-4 flex justify-end">
            <Button size="sm" variant="outline" onClick={onAddProduct}>
              <Plus className="mr-2 size-4" />
              {t("competitors.linkProduct")}
            </Button>
          </div>
          {isLoading ? (
            <div className="h-16 animate-pulse rounded bg-muted" />
          ) : competitorProducts.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {t("competitors.noProductsLinked")}
            </p>
          ) : (
            <div className="space-y-2">
              {competitorProducts.map((cp) => (
                <LinkedProductRow
                  key={cp.id}
                  cp={cp}
                  products={products}
                  locale={locale}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function LinkedProductRow({
  cp,
  products,
  locale,
}: {
  cp: CompetitorProduct;
  products: { id: string; name: string; sku: string | null }[];
  locale: string;
}) {
  const { t } = useTranslation();
  const productName =
    products.find((p) => p.id === cp.product_id)?.name ?? cp.name ?? t("common.dash");
  const trend =
    cp.price_diff != null
      ? cp.price_diff > 0
        ? ("up" as const)
        : cp.price_diff < 0
          ? ("down" as const)
          : ("stable" as const)
      : undefined;

  return (
    <div className="flex items-center justify-between gap-2 rounded-md border border-border bg-muted/30 px-3 py-2 dark:border-border dark:bg-muted/20">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{productName}</p>
        <a
          href={cp.url}
          target="_blank"
          rel="noopener noreferrer"
          className="truncate text-xs text-muted-foreground hover:underline"
        >
          {cp.url}
        </a>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {cp.last_price != null && (
          <span className="text-sm">{formatPrice(cp.last_price, "RUB", locale)}</span>
        )}
        {trend && (
          <TrendBadge
            trend={trend}
            value={cp.price_diff != null ? Math.abs(cp.price_diff) : undefined}
            size="sm"
          />
        )}
      </div>
    </div>
  );
}

function ExpandableCompetitorRow({
  competitor,
  benchmark,
  products,
  expanded,
  onToggle,
  onAddProduct,
}: {
  competitor: Competitor;
  benchmark?: { score: number; trend_30d: number[] };
  products: { id: string; name: string; sku: string | null }[];
  expanded: boolean;
  onToggle: () => void;
  onAddProduct: () => void;
}) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  const { data: competitorProducts = [], isLoading } = useQuery({
    queryKey: ["competitors", competitor.id, "products"],
    queryFn: async () => {
      const { data } = await competitorsApi.getProducts(competitor.id);
      return data;
    },
    enabled: expanded,
  });

  const marketplace = competitor.marketplace as Marketplace;
  const score = benchmark?.score ?? 0;
  const aggressiveness = score;

  return (
    <>
      <TableRow
        className="cursor-pointer transition-colors hover:bg-muted/50 dark:hover:bg-muted/50"
        onClick={onToggle}
      >
        <TableCell className="w-10">
          {expanded ? (
            <ChevronDown className="size-4" />
          ) : (
            <ChevronRight className="size-4" />
          )}
        </TableCell>
        <TableCell>
          <a
            href={competitor.website_url ?? "#"}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-medium text-primary hover:underline dark:text-primary"
            onClick={(e) => e.stopPropagation()}
          >
            {competitor.name}
            <ExternalLink className="size-4" />
          </a>
        </TableCell>
        <TableCell>
          <MarketplaceBadge marketplace={marketplace} size="sm" />
        </TableCell>
        <TableCell>
          <CircularScore value={score} size={32} strokeWidth={2} />
        </TableCell>
        <TableCell>{aggressiveness}%</TableCell>
        <TableCell>{competitor.product_count}</TableCell>
        <TableCell className="text-muted-foreground dark:text-muted-foreground">
          {formatDate(competitor.created_at, locale)}
        </TableCell>
      </TableRow>
      <TableRow className="bg-muted/30 dark:bg-muted/20">
        <TableCell colSpan={7} className="p-0">
          <div
            className={cn(
              "overflow-hidden transition-[max-height] duration-300 ease-in-out",
              expanded ? "max-h-[600px]" : "max-h-0"
            )}
          >
            <div className="border-t border-border px-4 py-4 dark:border-border">
              <div className="mb-4 flex justify-end">
                <Button size="sm" variant="outline" onClick={onAddProduct}>
                  <Plus className="mr-2 size-4" />
                  {t("competitors.linkProduct")}
                </Button>
              </div>
              {isLoading ? (
                <div className="h-24 animate-pulse rounded bg-muted" />
              ) : competitorProducts.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  {t("competitors.noProductsLinked")}
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("competitors.tableProduct")}</TableHead>
                      <TableHead>{t("competitors.tableUrl")}</TableHead>
                      <TableHead>{t("competitors.tablePrice")}</TableHead>
                      <TableHead></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {competitorProducts.map((cp) => (
                      <TableLinkedProductRow
                        key={cp.id}
                        cp={cp}
                        products={products}
                        locale={locale}
                      />
                    ))}
                  </TableBody>
                </Table>
              )}
            </div>
          </div>
        </TableCell>
      </TableRow>
    </>
  );
}

function TableLinkedProductRow({
  cp,
  products,
  locale,
}: {
  cp: CompetitorProduct;
  products: { id: string; name: string; sku: string | null }[];
  locale: string;
}) {
  const { t } = useTranslation();
  const productName =
    products.find((p) => p.id === cp.product_id)?.name ?? cp.name ?? t("common.dash");
  const trend =
    cp.price_diff != null
      ? cp.price_diff > 0
        ? ("up" as const)
        : cp.price_diff < 0
          ? ("down" as const)
          : ("stable" as const)
      : undefined;

  return (
    <TableRow>
      <TableCell className="font-medium">{productName}</TableCell>
      <TableCell className="max-w-48 truncate text-muted-foreground">
        <a href={cp.url} target="_blank" rel="noopener noreferrer" className="hover:underline">
          {cp.url}
        </a>
      </TableCell>
      <TableCell>
        {cp.last_price != null
          ? formatPrice(cp.last_price, "RUB", locale)
          : t("common.dash")}
      </TableCell>
      <TableCell>
        {trend && (
          <TrendBadge
            trend={trend}
            value={cp.price_diff != null ? Math.abs(cp.price_diff) : undefined}
            size="sm"
          />
        )}
      </TableCell>
    </TableRow>
  );
}

function AddCompetitorDialog({
  open,
  onOpenChange,
  form,
  setForm,
  onSubmit,
  isLoading,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  form: { name: string; website_url: string; marketplace: Marketplace };
  setForm: (f: (prev: typeof form) => typeof form) => void;
  onSubmit: (e: React.FormEvent) => void;
  isLoading: boolean;
}) {
  const { t } = useTranslation();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("competitors.addCompetitor")}</DialogTitle>
        </DialogHeader>
        <form onSubmit={onSubmit}>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("competitors.name")} *</label>
              <Input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("competitors.websiteUrl")}</label>
              <Input
                type="url"
                value={form.website_url}
                onChange={(e) => setForm((f) => ({ ...f, website_url: e.target.value }))}
                placeholder={t("competitors.urlPlaceholder")}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("competitors.marketplace")}</label>
              <SearchableMarketplaceSelect
                value={form.marketplace}
                onChange={(v) => setForm((f) => ({ ...f, marketplace: v }))}
                placeholder={t("competitors.selectMarketplace")}
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={isLoading}>
              {t("common.add")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function AddCompetitorProductDialog({
  open,
  onOpenChange,
  competitorName,
  form,
  setForm,
  products,
  onSubmit,
  onAutoDetect,
  isLoading,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  competitorName: string;
  form: { product_id: string; url: string; scraper_type: ScraperType };
  setForm: (f: (prev: typeof form) => typeof form) => void;
  products: { id: string; name: string; sku: string | null }[];
  onSubmit: (e: React.FormEvent) => void;
  onAutoDetect: () => void;
  isLoading: boolean;
}) {
  const { t } = useTranslation();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("competitors.linkTo", { name: competitorName })}</DialogTitle>
        </DialogHeader>
        <form onSubmit={onSubmit}>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("competitors.myProduct")} *</label>
              <SearchableProductSelect
                value={form.product_id}
                onChange={(v) => setForm((f) => ({ ...f, product_id: v }))}
                products={products}
                placeholder={t("competitors.selectProduct")}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("competitors.productUrl")} *</label>
              <Input
                type="url"
                value={form.url}
                onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))}
                placeholder={t("products.urlPlaceholder")}
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("competitors.scraper")}</label>
              <div className="flex gap-2">
                <Select
                  value={form.scraper_type}
                  onValueChange={(v) =>
                    setForm((f) => ({ ...f, scraper_type: v as ScraperType }))
                  }
                >
                  <SelectTrigger className="flex-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(["auto", "ozon_api", "wb_api", "css_selector", "json_api"] as const).map((k) => (
                      <SelectItem key={k} value={k}>
                        {t(getScraperLabel(k))}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  onClick={onAutoDetect}
                  title={t("competitors.autoDetect")}
                  aria-label={t("competitors.autoDetect")}
                >
                  <Wand2 className="size-4" />
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                {t("competitors.autoDetect")}
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={isLoading}>
              {t("competitors.linkProduct")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
