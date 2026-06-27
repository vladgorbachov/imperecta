import { apiClient } from "./client";

export interface NewsItem {
  title: string;
  source: string;
  published_at: string;
  snippet: string;
  url: string;
  image_url?: string | null;
}

export interface NewsResponse {
  items: NewsItem[];
  source_provider: string;
}

export interface NewsParams {
  country_code?: string;
  language?: string;
}

export const newsApi = {
  getNews: (params?: NewsParams) =>
    apiClient.get<NewsResponse>("/news", { params }),
};

export const newsQueryKeys = {
  news: (params?: NewsParams) =>
    [
      "news",
      {
        country_code: params?.country_code ?? null,
        language: params?.language ?? "en",
      },
    ] as const,
};
