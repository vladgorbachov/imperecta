import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Plus, ChevronDown, ChevronRight } from "lucide-react";
import { format } from "date-fns";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { competitorsApi } from "@/api/competitors";
import { productsApi } from "@/api/products";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import type { Competitor } from "@/api/competitors";

const MARKETPLACE_LABELS: Record<string, string> = {
  ozon: "Ozon",
  wildberries: "WB",
  kaspi: "Kaspi",
  custom: "Custom",
};

export function CompetitorsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [addCompetitorOpen, setAddCompetitorOpen] = useState(false);
  const [addProductOpen, setAddProductOpen] = useState(false);
  const [selectedCompetitor, setSelectedCompetitor] = useState<Competitor | null>(null);
  const [competitorForm, setCompetitorForm] = useState({
    name: "",
    website_url: "",
    marketplace: "custom",
  });
  const [productForm, setProductForm] = useState({
    product_id: "",
    url: "",
    scraper_type: "auto",
  });

  const { data: competitors = [], isLoading } = useQuery({
    queryKey: ["competitors"],
    queryFn: async () => {
      const { data } = await competitorsApi.list();
      return data;
    },
  });

  const { data: products = [] } = useQuery({
    queryKey: ["products"],
    queryFn: async () => {
      const { data } = await productsApi.list({ limit: 500 });
      return data.items;
    },
  });

  const createMutation = useMutation({
    mutationFn: competitorsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["competitors"] });
      setAddCompetitorOpen(false);
      setCompetitorForm({ name: "", website_url: "", marketplace: "custom" });
      toast.success("Competitor added");
    },
    onError: () => toast.error("Failed to add competitor"),
  });

  const addProductMutation = useMutation({
    mutationFn: competitorsApi.addProduct,
    onSuccess: () => {
      if (selectedCompetitor) {
        queryClient.invalidateQueries({
          queryKey: ["competitors", selectedCompetitor.id, "products"],
        });
        queryClient.invalidateQueries({ queryKey: ["competitors"] });
      }
      setAddProductOpen(false);
      setProductForm({ product_id: "", url: "", scraper_type: "auto" });
      toast.success("Product linked");
    },
    onError: () => toast.error("Failed to link product"),
  });

  const handleAddCompetitor = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate({
      name: competitorForm.name,
      website_url: competitorForm.website_url || undefined,
      marketplace: competitorForm.marketplace as "ozon" | "wildberries" | "kaspi" | "custom",
    });
  };

  const handleAddProduct = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCompetitor) return;
    addProductMutation.mutate({
      product_id: productForm.product_id,
      competitor_id: selectedCompetitor.id,
      url: productForm.url,
      scraper_type: productForm.scraper_type,
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("nav.competitors")}</h1>
        <Button onClick={() => setAddCompetitorOpen(true)}>
          <Plus className="mr-2 size-4" />
          Add competitor
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {competitors.map((c) => (
            <CompetitorRow
              key={c.id}
              competitor={c}
              products={products}
              onAddProduct={() => {
                setSelectedCompetitor(c);
                setAddProductOpen(true);
              }}
            />
          ))}
          {competitors.length === 0 && (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                No competitors yet. Add one to get started.
              </CardContent>
            </Card>
          )}
        </div>
      )}

      <Dialog open={addCompetitorOpen} onOpenChange={setAddCompetitorOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add competitor</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleAddCompetitor}>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Name *</label>
                <Input
                  value={competitorForm.name}
                  onChange={(e) =>
                    setCompetitorForm((f) => ({ ...f, name: e.target.value }))
                  }
                  required
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Website URL</label>
                <Input
                  type="url"
                  value={competitorForm.website_url}
                  onChange={(e) =>
                    setCompetitorForm((f) => ({ ...f, website_url: e.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Marketplace</label>
                <Select
                  value={competitorForm.marketplace}
                  onValueChange={(v) =>
                    setCompetitorForm((f) => ({ ...f, marketplace: v }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {["ozon", "wildberries", "kaspi", "custom"].map((m) => (
                      <SelectItem key={m} value={m}>
                        {MARKETPLACE_LABELS[m]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setAddCompetitorOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                Add
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={addProductOpen} onOpenChange={setAddProductOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Link product to {selectedCompetitor?.name}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleAddProduct}>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Product *</label>
                <Select
                  value={productForm.product_id}
                  onValueChange={(v) =>
                    setProductForm((f) => ({ ...f, product_id: v }))
                  }
                  required
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select product" />
                  </SelectTrigger>
                  <SelectContent>
                    {products.map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.name} ({p.sku || p.id.slice(0, 8)})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Product URL *</label>
                <Input
                  type="url"
                  value={productForm.url}
                  onChange={(e) =>
                    setProductForm((f) => ({ ...f, url: e.target.value }))
                  }
                  placeholder="https://..."
                  required
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Scraper</label>
                <Select
                  value={productForm.scraper_type}
                  onValueChange={(v) =>
                    setProductForm((f) => ({ ...f, scraper_type: v }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="auto">Auto-detect</SelectItem>
                    <SelectItem value="ozon">Ozon</SelectItem>
                    <SelectItem value="wildberries">Wildberries</SelectItem>
                    <SelectItem value="generic">Generic</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setAddProductOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={addProductMutation.isPending}>
                Link
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function CompetitorRow({
  competitor,
  products,
  onAddProduct,
}: {
  competitor: Competitor;
  products: { id: string; name: string; sku: string | null }[];
  onAddProduct: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const { data: competitorProducts = [], isLoading } = useQuery({
    queryKey: ["competitors", competitor.id, "products"],
    queryFn: async () => {
      const { data } = await competitorsApi.getProducts(competitor.id);
      return data;
    },
    enabled: expanded,
  });

  const badgeLabel = MARKETPLACE_LABELS[competitor.marketplace] ?? competitor.marketplace;

  return (
    <Card>
      <CardHeader
        className="cursor-pointer py-4"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {expanded ? (
              <ChevronDown className="size-4" />
            ) : (
              <ChevronRight className="size-4" />
            )}
            <div>
              <CardTitle className="text-base">{competitor.name}</CardTitle>
              <p className="text-sm text-muted-foreground">
                {competitor.website_url || "—"} · {competitor.product_count}{" "}
                products
              </p>
            </div>
            <Badge variant="secondary">{badgeLabel}</Badge>
          </div>
        </div>
      </CardHeader>
      {expanded && (
        <CardContent className="border-t pt-4">
          <div className="mb-4 flex justify-end">
            <Button size="sm" variant="outline" onClick={onAddProduct}>
              <Plus className="mr-2 size-4" />
              Link product
            </Button>
          </div>
          {isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : competitorProducts.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No products linked. Click "Link product" to add.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Product</TableHead>
                  <TableHead>URL</TableHead>
                  <TableHead>Price</TableHead>
                  <TableHead>Last checked</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {competitorProducts.map((cp) => (
                  <TableRow key={cp.id}>
                    <TableCell className="font-medium">
                      {cp.name || products.find((p) => p.id === cp.product_id)?.name || "—"}
                    </TableCell>
                    <TableCell className="max-w-48 truncate text-muted-foreground">
                      {cp.url}
                    </TableCell>
                    <TableCell>
                      {cp.last_price != null
                        ? `${Number(cp.last_price).toFixed(2)} ₽`
                        : "—"}
                    </TableCell>
                    <TableCell>
                      {cp.last_checked_at
                        ? format(new Date(cp.last_checked_at), "dd.MM.yyyy HH:mm")
                        : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      )}
    </Card>
  );
}
