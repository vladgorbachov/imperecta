import { apiClient } from "./client";

export interface ImportResult {
  imported: number;
  errors: { row: number; message: string }[];
}

export interface PreviewResult {
  preview: Record<string, string>[];
  errors: { row: number; message: string }[];
}

export const importApi = {
  uploadProductsCsv: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient.post<ImportResult>("/import/products/csv", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  previewProductsCsv: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient.post<PreviewResult>("/import/products/preview", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  getProductsTemplateUrl: () => "/api/import/products/template",
};
