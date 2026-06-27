import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { newsApi, newsQueryKeys } from "@/api/news";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { Skeleton } from "@/components/ui/skeleton";
import { formatRelativeTime } from "@/lib/formatters";
import { formatNewsSource } from "@/lib/formatNewsSource";
import { cn } from "@/lib/utils";

const MAX_ITEMS = 8;

export interface MarketNewsWidgetProps {
  countryCode: string | null;
}

function NewsSkeleton() {
  return (
    <div className="space-y-4" data-testid="news-skeleton">
      {Array.from({ length: 4 }, (_, index) => (
        <div key={index} className="flex gap-4 rounded-lg border border-border/50 p-4">
          <Skeleton className="hidden size-20 shrink-0 rounded-md sm:block" />
          <div className="min-w-0 flex-1 space-y-2">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-1/3" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-5/6" />
          </div>
        </div>
      ))}
    </div>
  );
}

function NewsItemCard({
  item,
  locale,
}: {
  item: {
    title: string;
    source: string;
    published_at: string;
    snippet: string;
    url: string;
    image_url?: string | null;
  };
  locale: string;
}) {
  const [imageHidden, setImageHidden] = useState(false);
  const sourceLabel = useMemo(() => formatNewsSource(item.source), [item.source]);
  const publishedLabel = useMemo(() => {
    const parsed = new Date(item.published_at);
    if (Number.isNaN(parsed.getTime())) {
      return null;
    }
    return formatRelativeTime(parsed, locale);
  }, [item.published_at, locale]);

  return (
    <article className="flex gap-4 rounded-lg border border-border/50 bg-muted/20 p-4 transition-colors hover:bg-muted/30">
      {item.image_url && !imageHidden ? (
        <img
          src={item.image_url}
          alt=""
          loading="lazy"
          className="hidden aspect-[4/3] w-20 shrink-0 rounded-md object-cover sm:block"
          onError={() => setImageHidden(true)}
        />
      ) : null}
      <div className="min-w-0 flex-1 space-y-1.5">
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className={cn(
            "line-clamp-2 break-words text-sm font-medium leading-snug text-foreground",
            "underline-offset-2 hover:underline",
          )}
        >
          {item.title}
        </a>
        {sourceLabel || publishedLabel ? (
          <p className="truncate text-xs text-muted-foreground">
            {sourceLabel ? (
              <span className="font-medium text-foreground/80">{sourceLabel}</span>
            ) : null}
            {sourceLabel && publishedLabel ? (
              <span aria-hidden className="mx-1.5">
                ·
              </span>
            ) : null}
            {publishedLabel ? (
              <time dateTime={item.published_at}>{publishedLabel}</time>
            ) : null}
          </p>
        ) : null}
        {item.snippet ? (
          <p className="line-clamp-3 break-words text-sm leading-relaxed text-muted-foreground">
            {item.snippet}
          </p>
        ) : null}
      </div>
    </article>
  );
}

export function MarketNewsWidget({ countryCode }: MarketNewsWidgetProps) {
  const { t, i18n } = useTranslation();
  const queryParams = useMemo(
    () => ({
      country_code: countryCode ?? undefined,
      language: "en" as const,
    }),
    [countryCode],
  );

  const { data, isLoading, isError } = useQuery({
    queryKey: newsQueryKeys.news(queryParams),
    queryFn: () => newsApi.getNews(queryParams).then((response) => response.data),
    staleTime: 60_000,
  });

  const items = useMemo(() => (data?.items ?? []).slice(0, MAX_ITEMS), [data?.items]);

  return (
    <section
      className={cn(
        "surface-base surface-liquid flex h-full min-h-0 flex-col rounded-xl p-4 sm:p-5",
      )}
      aria-labelledby="market-news-heading"
      data-testid="market-news-widget"
    >
      <header className="mb-4 shrink-0 space-y-1">
        <h2 id="market-news-heading" className="text-base font-semibold sm:text-lg">
          {t("market.news.title")}
        </h2>
        <p className="text-xs text-muted-foreground sm:text-sm">{t("market.news.subtitle")}</p>
      </header>

      <div className="flex min-h-0 flex-1 flex-col">
        {isLoading ? (
          <NewsSkeleton />
        ) : isError ? (
          <p className="text-sm text-muted-foreground" role="status">
            {t("market.news.loadError")}
          </p>
        ) : items.length === 0 ? (
          <EmptyState
            title="market.news.unavailable"
            description="market.news.unavailableHint"
            className="py-8"
          />
        ) : (
          <ul className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-0.5">
            {items.map((item) => (
              <li key={`${item.url}-${item.published_at}`}>
                <NewsItemCard item={item} locale={i18n.language} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
