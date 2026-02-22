import { useState } from "react";
import { useTranslation } from "react-i18next";
import { format } from "date-fns";
import { useQuery } from "@tanstack/react-query";
import { digestsApi } from "@/api/digests";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function DigestsPage() {
  const { t } = useTranslation();
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data: digests = [], isLoading } = useQuery({
    queryKey: ["digests"],
    queryFn: async () => {
      const { data } = await digestsApi.list();
      return data;
    },
  });

  const { data: expandedDigest } = useQuery({
    queryKey: ["digests", expandedId],
    queryFn: async () => {
      if (!expandedId) return null;
      const { data } = await digestsApi.get(expandedId);
      return data;
    },
    enabled: !!expandedId,
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">{t("nav.digests")}</h1>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : digests.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No digests yet.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {digests.map((d) => (
            <Card key={d.id}>
              <CardHeader
                className="cursor-pointer"
                onClick={() =>
                  setExpandedId(expandedId === d.id ? null : d.id)
                }
              >
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-base">
                      {d.period_type === "daily" ? "Daily" : "Weekly"} digest
                    </CardTitle>
                    <p className="text-sm text-muted-foreground">
                      {format(new Date(d.period_start), "dd.MM.yyyy")} —{" "}
                      {format(new Date(d.period_end), "dd.MM.yyyy")} · Created{" "}
                      {format(new Date(d.created_at), "dd.MM.yyyy HH:mm")}
                    </p>
                  </div>
                  <Badge variant={d.sent_at ? "default" : "secondary"}>
                    {d.sent_at ? "Sent" : "Draft"}
                  </Badge>
                </div>
              </CardHeader>
              {expandedId === d.id && (
                <CardContent className="border-t pt-4">
                  {expandedDigest?.id === d.id ? (
                    <div
                      className="prose prose-sm dark:prose-invert max-w-none"
                      dangerouslySetInnerHTML={{
                        __html: renderMarkdown(expandedDigest.content_md),
                      }}
                    />
                  ) : (
                    <Skeleton className="h-32 w-full" />
                  )}
                </CardContent>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function renderMarkdown(md: string): string {
  if (!md) return "";
  return md
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/^### (.*)$/gim, "<h3>$1</h3>")
    .replace(/^## (.*)$/gim, "<h2>$1</h2>")
    .replace(/^# (.*)$/gim, "<h1>$1</h1>")
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    .replace(/^- (.*)$/gim, "<li>$1</li>")
    .replace(/\n\n/g, "</p><p>")
    .replace(/\n/g, "<br/>")
    .replace(/^(.+)$/gim, "<p>$1</p>");
}
