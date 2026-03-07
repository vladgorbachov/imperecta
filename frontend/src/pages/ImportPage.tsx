// MOBILE-2026: fully responsive + bottom nav + drawer

/**
 * Import page: 3-step flow — upload zone, preview with column mapping, import + results.
 *
 * i18n keys used:
 * - nav.import
 * - import.dropzoneCsv, import.or, import.selectFile, import.changeFile
 * - import.downloadTemplate, import.previewTitle
 * - import.columnName, import.columnSku, import.columnPrice, import.columnUrl, import.columnCategory
 * - import.ignore, import.importProducts, import.importMore
 * - import.imported, import.errors, import.rowError
 * - common.loading
 */

import { useState, useRef, useCallback, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Upload, Download, CheckCircle, ChevronDown, ChevronUp, FileSpreadsheet } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { importApi } from "@/api/import";
import { apiBaseUrl } from "@/api/client";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import { PageHeader } from "@/components/ui-custom/PageHeader";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

const KNOWN_COLUMNS = ["name", "sku", "price", "url", "category"] as const;
const REQUIRED_COLUMNS = ["name", "price"] as const;
const COLUMN_KEYS: Record<(typeof KNOWN_COLUMNS)[number], string> = {
  name: "import.columnName",
  sku: "import.columnSku",
  price: "import.columnPrice",
  url: "import.columnUrl",
  category: "import.columnCategory",
};

function parseCsv(
  text: string
): { headers: string[]; rows: string[][]; allRows: string[][]; totalRows: number } {
  const lines = text.split(/\r?\n/).filter((l) => l.length > 0);
  if (lines.length === 0) return { headers: [], rows: [], allRows: [], totalRows: 0 };
  const parseRow = (line: string): string[] => {
    const result: string[] = [];
    let current = "";
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
      const c = line[i];
      if (c === '"') {
        inQuotes = !inQuotes;
      } else if ((c === "," && !inQuotes) || (c === ";" && !inQuotes)) {
        result.push(current.trim());
        current = "";
      } else {
        current += c;
      }
    }
    result.push(current.trim());
    return result;
  };
  const headers = parseRow(lines[0]);
  const allRows = lines.slice(1).map(parseRow);
  const rows = allRows.slice(0, 5);
  return { headers, rows, allRows, totalRows: allRows.length };
}

function autoMapColumn(header: string): (typeof KNOWN_COLUMNS)[number] | null {
  const lower = header.toLowerCase().trim();
  const aliases: Record<string, (typeof KNOWN_COLUMNS)[number]> = {
    name: "name",
    nazvanie: "name",
    название: "name",
    product: "name",
    title: "name",
    product_name: "name",
    sku: "sku",
    артикул: "sku",
    article: "sku",
    price: "price",
    цена: "price",
    cost: "price",
    url: "url",
    link: "url",
    ссылка: "url",
    category: "category",
    категория: "category",
    marketplace: "category",
  };
  const normalized = lower.replace(/\s+/g, "_");
  return aliases[normalized] ?? aliases[lower] ?? null;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ImportPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [headers, setHeaders] = useState<string[]>([]);
  const [rows, setRows] = useState<string[][]>([]);
  const [allRows, setAllRows] = useState<string[][]>([]);
  const [totalRows, setTotalRows] = useState(0);
  const [columnMap, setColumnMap] = useState<Record<string, string>>({});
  const [importing, setImporting] = useState(false);
  const [importProgress, setImportProgress] = useState(0);
  const [result, setResult] = useState<{
    imported: number;
    errors: { row: number; message: string }[];
  } | null>(null);
  const [errorsExpanded, setErrorsExpanded] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [productsWithoutCategory, setProductsWithoutCategory] = useState(0);
  const [autoCategorizeDismissed, setAutoCategorizeDismissed] = useState(false);

  const handleFileSelect = useCallback(
    async (selectedFile: File) => {
      if (!selectedFile.name.toLowerCase().endsWith(".csv")) {
        toast.error(t("import.fileFormatError"));
        return;
      }
      setFile(selectedFile);
      setResult(null);
      const text = await selectedFile.text();
      const { headers: h, rows: r, allRows: ar, totalRows: tr } = parseCsv(text);
      setHeaders(h);
      setRows(r);
      setAllRows(ar);
      setTotalRows(tr);
      const map: Record<string, string> = {};
      h.forEach((header) => {
        const mapped = autoMapColumn(header);
        if (mapped) map[header] = mapped;
        else map[header] = "";
      });
      setColumnMap(map);
      setAutoCategorizeDismissed(false);
    },
    [t]
  );

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) handleFileSelect(f);
    e.target.value = "";
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) handleFileSelect(f);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => setDragOver(false);

  const handleChangeFile = () => {
    setFile(null);
    setHeaders([]);
    setRows([]);
    setAllRows([]);
    setColumnMap({});
    setResult(null);
    setProductsWithoutCategory(0);
    setAutoCategorizeDismissed(false);
    fileInputRef.current?.click();
  };

  // Recompute productsWithoutCategory when column mapping changes
  useEffect(() => {
    if (headers.length === 0 || allRows.length === 0) return;
    const catHeader = headers.find((h) => columnMap[h] === "category") ?? null;
    const catIdx = catHeader ? headers.indexOf(catHeader) : -1;
    const count =
      catIdx >= 0 ? allRows.filter((row) => !(row[catIdx] ?? "").trim()).length : 0;
    setProductsWithoutCategory(count);
  }, [headers, columnMap, allRows]);

  const handleMappingChange = (header: string, value: string) => {
    setColumnMap((prev) => ({ ...prev, [header]: value }));
  };

  const mappedColumns = Object.values(columnMap).filter(Boolean);
  const requiredMapped = REQUIRED_COLUMNS.every((r) => mappedColumns.includes(r));
  const productCount = totalRows;

  const handleImport = async () => {
    if (!file || !requiredMapped) return;
    setImporting(true);
    setImportProgress(0);
    setResult(null);
    try {
      setImportProgress(30);
      const text = await file.text();
      const { headers: h, allRows } = parseCsv(text);
      const revMap: Record<string, string> = {};
      h.forEach((header) => {
        const target = columnMap[header];
        if (target) revMap[target] = header;
      });
      const csvLines: string[] = [KNOWN_COLUMNS.join(",")];
      for (const row of allRows) {
        const obj: Record<string, string> = {};
        h.forEach((header, i) => {
          obj[header] = row[i] ?? "";
        });
        const mappedRow = KNOWN_COLUMNS.map((col) => {
          const src = revMap[col];
          return src ? (obj[src] ?? "") : "";
        });
        csvLines.push(mappedRow.map((c) => (c.includes(",") ? `"${c}"` : c)).join(","));
      }
      setImportProgress(60);
      const blob = new Blob([csvLines.join("\n")], { type: "text/csv" });
      const transformedFile = new File([blob], file.name, { type: "text/csv" });
      const { data } = await importApi.uploadProductsCsv(transformedFile);
      setImportProgress(100);
      queryClient.invalidateQueries({ queryKey: ["products"] });
      setResult({ imported: data.imported, errors: data.errors ?? [] });
      toast.success(t("import.success", { count: data.imported }));
      if (data.errors?.length) {
        toast.error(t("import.errorsCount", { count: data.errors.length }));
      }
    } catch {
      toast.error(t("import.error"));
      setResult({ imported: 0, errors: [{ row: 0, message: t("import.error") }] });
    } finally {
      setImporting(false);
      setImportProgress(0);
    }
  };

  const handleImportMore = () => {
    setResult(null);
    handleChangeFile();
  };

  const downloadTemplate = async () => {
    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch(`${apiBaseUrl}/import/products/template`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "products_template.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error(t("import.error"));
    }
  };

  const hasResult = result !== null;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader title="nav.import" />

      <input
        ref={fileInputRef}
        type="file"
        accept=".csv"
        className="hidden"
        onChange={handleInputChange}
      />

      {!file && (
        <Card>
          <CardContent className="p-0">
            <div
              className={cn(
                "flex min-h-48 flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-8 transition-all duration-200",
                "border-accent/30 bg-accent/5 dark:border-accent/40 dark:bg-accent/10",
                dragOver && "scale-[1.02] border-accent bg-accent/10 dark:bg-accent/20"
              )}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
            >
              <Upload className="size-12 text-accent dark:text-accent" />
              <p className="text-center text-sm font-medium">
                {t("import.dropzoneCsv")}
              </p>
              <p className="text-sm text-muted-foreground dark:text-muted-foreground">
                {t("import.or")}
              </p>
              <Button
                variant="default"
                onClick={() => fileInputRef.current?.click()}
              >
                {t("import.selectFile")}
              </Button>
            </div>
            <div className="flex justify-center border-t border-border p-4">
              <button
                type="button"
                onClick={downloadTemplate}
                className="inline-flex items-center gap-2 text-sm text-primary hover:underline dark:text-primary"
              >
                <Download className="size-4" />
                {t("import.downloadTemplate")}
              </button>
            </div>
          </CardContent>
        </Card>
      )}

      {file && !hasResult && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-muted/30 px-4 py-3 dark:bg-muted/20">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">{file.name}</span>
              <span className="text-xs text-muted-foreground dark:text-muted-foreground">
                {formatFileSize(file.size)}
              </span>
            </div>
            <button
              type="button"
              onClick={handleChangeFile}
              className="text-sm text-primary hover:underline dark:text-primary"
            >
              {t("import.changeFile")}
            </button>
          </div>

          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      {headers.map((header) => {
                        const mapped = columnMap[header];
                        const requiredUnmapped = !requiredMapped;
                        return (
                          <TableHead
                            key={header}
                            className={cn(
                              requiredUnmapped && "bg-amber-500/15 dark:bg-amber-500/20"
                            )}
                          >
                            <div className="flex flex-col gap-1">
                              <span>{header}</span>
                              <Select
                                value={mapped || "ignore"}
                                onValueChange={(v) =>
                                  handleMappingChange(header, v === "ignore" ? "" : v)
                                }
                              >
                                <SelectTrigger className="h-8 text-xs">
                                  <SelectValue placeholder={t("import.ignore")} />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="ignore">
                                    {t("import.ignore")}
                                  </SelectItem>
                                  {KNOWN_COLUMNS.map((col) => (
                                    <SelectItem key={col} value={col}>
                                      <span className="flex items-center gap-2">
                                        {t(COLUMN_KEYS[col])}
                                        {autoMapColumn(header) === col && (
                                          <CheckCircle className="size-3.5 text-green-600 dark:text-green-500" />
                                        )}
                                      </span>
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                            </div>
                          </TableHead>
                        );
                      })}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((row, i) => (
                      <TableRow key={i}>
                        {headers.map((header, j) => (
                          <TableCell
                            key={header}
                            className="max-w-32 truncate text-sm"
                          >
                            {row[j] ?? ""}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>

          {importing && (
            <div className="space-y-2">
              <Progress value={importProgress} />
              <p className="text-center text-sm text-muted-foreground dark:text-muted-foreground">
                {t("import.importing")} {Math.round(importProgress)}%
              </p>
            </div>
          )}

          {productsWithoutCategory > 0 && !autoCategorizeDismissed && (
            <Card className="border-primary/30 bg-primary/5 dark:border-primary/20 dark:bg-primary/10">
              <CardContent className="space-y-4 pt-6">
                <p className="text-sm font-medium">
                  {t("import.aiNoCategories", { count: productsWithoutCategory })}
                </p>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    onClick={() => {
                      // TODO: POST /api/import/auto-categorize
                      toast.info(t("common.comingSoon"));
                      setAutoCategorizeDismissed(true);
                    }}
                  >
                    {t("import.aiAssignYes")}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setAutoCategorizeDismissed(true)}
                  >
                    {t("import.aiAssignNo")}
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {!importing && (
            <Button
              size="lg"
              className="w-full"
              onClick={handleImport}
              disabled={!requiredMapped || productCount === 0}
            >
              {t("import.importProducts", { count: productCount })}
            </Button>
          )}

          <Button
            variant="outline"
            className="w-full"
            disabled
            aria-disabled
          >
            <FileSpreadsheet className="mr-2 size-4" />
            {t("import.exportStrategicReport")}
            <Badge variant="secondary" className="ml-2">
              {t("common.comingSoon")}
            </Badge>
          </Button>
        </>
      )}

      {hasResult && result && (
        <Card>
          <CardContent className="space-y-4 pt-6">
            <div className="flex items-center gap-2 text-green-600 dark:text-green-500">
              <CheckCircle className="size-5 shrink-0" />
              <span className="font-medium">
                {t("import.imported")}: {result.imported}
              </span>
            </div>

            {result.errors.length > 0 && (
              <div className="space-y-2">
                <button
                  type="button"
                  className="flex w-full items-center justify-between rounded-md border border-border bg-muted/30 px-3 py-2 text-left text-sm font-medium hover:bg-muted/50 dark:bg-muted/20 dark:hover:bg-muted/30"
                  onClick={() => setErrorsExpanded((e) => !e)}
                >
                  <span className="text-destructive dark:text-destructive">
                    {t("import.errors")}: {result.errors.length}
                  </span>
                  {errorsExpanded ? (
                    <ChevronUp className="size-4" />
                  ) : (
                    <ChevronDown className="size-4" />
                  )}
                </button>
                {errorsExpanded && (
                  <ul className="list-inside list-disc space-y-1 text-sm text-destructive dark:text-destructive">
                    {result.errors.map((e, i) => (
                      <li key={i}>
                        {t("import.rowError", { row: e.row, message: e.message })}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            <Button variant="outline" className="w-full" onClick={handleImportMore}>
              {t("import.importMore")}
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
