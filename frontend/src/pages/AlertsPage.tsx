import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Plus } from "lucide-react";
import { format } from "date-fns";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { alertsApi } from "@/api/alerts";
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

const ALERT_TYPE_LABELS: Record<string, string> = {
  price_drop: "Price drop",
  price_increase: "Price increase",
  out_of_stock: "Out of stock",
  new_promo: "New promo",
};

const CHANNEL_LABELS: Record<string, string> = {
  email: "Email",
  telegram: "Telegram",
  both: "Both",
};

export function AlertsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState({
    product_id: "",
    type: "price_drop",
    threshold_percent: "",
    channel: "email",
  });

  const { data: alerts = [], isLoading } = useQuery({
    queryKey: ["alerts"],
    queryFn: async () => {
      const { data } = await alertsApi.list();
      return data;
    },
  });

  const { data: events = [] } = useQuery({
    queryKey: ["alerts", "events"],
    queryFn: async () => {
      const { data } = await alertsApi.getEvents(20);
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
    mutationFn: alertsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      setCreateOpen(false);
      setForm({ product_id: "", type: "price_drop", threshold_percent: "", channel: "email" });
      toast.success("Alert created");
    },
    onError: () => toast.error("Failed to create alert"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      alertsApi.update(id, { is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate({
      product_id: form.product_id || undefined,
      type: form.type,
      threshold_percent: form.threshold_percent ? parseFloat(form.threshold_percent) : undefined,
      channel: form.channel,
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("nav.alerts")}</h1>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 size-4" />
          Create alert
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Active rules</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : alerts.length === 0 ? (
            <p className="text-muted-foreground">No alerts yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Product</TableHead>
                  <TableHead>Threshold</TableHead>
                  <TableHead>Channel</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {alerts.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell>
                      <Badge variant="secondary">
                        {ALERT_TYPE_LABELS[a.type] ?? a.type}
                      </Badge>
                    </TableCell>
                    <TableCell>{a.product_name ?? "All products"}</TableCell>
                    <TableCell>
                      {a.threshold_percent != null
                        ? `${a.threshold_percent}%`
                        : "—"}
                    </TableCell>
                    <TableCell>{CHANNEL_LABELS[a.channel] ?? a.channel}</TableCell>
                    <TableCell>
                      <Button
                        variant={a.is_active ? "default" : "outline"}
                        size="sm"
                        onClick={() =>
                          updateMutation.mutate({
                            id: a.id,
                            is_active: !a.is_active,
                          })
                        }
                      >
                        {a.is_active ? "On" : "Off"}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent events (last 20)</CardTitle>
        </CardHeader>
        <CardContent>
          {events.length === 0 ? (
            <p className="text-muted-foreground">No events yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Product</TableHead>
                  <TableHead>Competitor</TableHead>
                  <TableHead>Change</TableHead>
                  <TableHead>Sent via</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {events.map((e) => (
                  <TableRow key={e.id}>
                    <TableCell>
                      {format(new Date(e.triggered_at), "dd.MM.yyyy HH:mm")}
                    </TableCell>
                    <TableCell>{e.product_name ?? "—"}</TableCell>
                    <TableCell>{e.competitor_name ?? "—"}</TableCell>
                    <TableCell>
                      {e.old_price != null && e.new_price != null
                        ? `${Number(e.old_price).toFixed(2)} → ${Number(e.new_price).toFixed(2)} ₽`
                        : e.message}
                    </TableCell>
                    <TableCell>{e.sent_via}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create alert</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate}>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Product</label>
                <Select
                  value={form.product_id}
                  onValueChange={(v) => setForm((f) => ({ ...f, product_id: v }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="All products" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">All products</SelectItem>
                    {products.map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Type</label>
                <Select
                  value={form.type}
                  onValueChange={(v) => setForm((f) => ({ ...f, type: v }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {["price_drop", "price_increase", "out_of_stock", "new_promo"].map(
                      (t) => (
                        <SelectItem key={t} value={t}>
                          {ALERT_TYPE_LABELS[t]}
                        </SelectItem>
                      )
                    )}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Threshold %</label>
                <Input
                  type="number"
                  step="0.1"
                  min="0"
                  max="100"
                  value={form.threshold_percent}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, threshold_percent: e.target.value }))
                  }
                  placeholder="e.g. 10"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Channel</label>
                <Select
                  value={form.channel}
                  onValueChange={(v) => setForm((f) => ({ ...f, channel: v }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {["email", "telegram", "both"].map((c) => (
                      <SelectItem key={c} value={c}>
                        {CHANNEL_LABELS[c]}
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
                onClick={() => setCreateOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                Create
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
