import { useState, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Upload, Download } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { importApi } from "@/api/import";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";

export function ImportPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Record<string, string>[]>([]);
  const [previewErrors, setPreviewErrors] = useState<{ row: number; message: string }[]>([]);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<{
    imported: number;
    errors: { row: number; message: string }[];
  } | null>(null);

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;

    setFile(selectedFile);
    setResult(null);

    const ext = selectedFile.name.toLowerCase().slice(-4);
    if (!ext.endsWith(".csv") && !selectedFile.name.toLowerCase().endsWith(".xlsx") && !selectedFile.name.toLowerCase().endsWith(".xls")) {
      setPreview([]);
      setPreviewErrors([{ row: 0, message: "Use CSV or Excel file" }]);
      return;
    }

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      const { data } = await importApi.previewProductsCsv(selectedFile);
      setPreview(data.preview ?? []);
      setPreviewErrors(data.errors ?? []);
    } catch {
      setPreview([]);
      setPreviewErrors([{ row: 0, message: "Failed to parse file" }]);
    }

    e.target.value = "";
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile) {
      const input = fileInputRef.current;
      if (input) {
        const dt = new DataTransfer();
        dt.items.add(droppedFile);
        input.files = dt.files;
        input.dispatchEvent(new Event("change", { bubbles: true }));
      }
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleImport = async () => {
    if (!file) return;
    setImporting(true);
    setResult(null);
    try {
      const { data } = await importApi.uploadProductsCsv(file);
      queryClient.invalidateQueries({ queryKey: ["products"] });
      setResult({ imported: data.imported, errors: data.errors ?? [] });
      toast.success(`Imported: ${data.imported}`);
      if (data.errors?.length) {
        toast.error(`Errors: ${data.errors.length}`);
      }
    } catch {
      toast.error("Import failed");
    } finally {
      setImporting(false);
    }
  };

  const templateUrl = "/api/import/products/template";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">{t("nav.import")}</h1>

      <Card>
        <CardHeader>
          <CardTitle>Upload file</CardTitle>
          <p className="text-sm text-muted-foreground">
            CSV or Excel. Columns: name, sku, price, url, category
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.xlsx,.xls"
            className="hidden"
            onChange={handleFileSelect}
          />
          <div
            className="flex min-h-32 flex-col items-center justify-center rounded-lg border-2 border-dashed border-muted-foreground/25 bg-muted/30 p-6 transition-colors hover:border-muted-foreground/50"
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload className="mb-2 size-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Drag and drop or click to select
            </p>
            {file && (
              <p className="mt-2 text-sm font-medium">{file.name}</p>
            )}
          </div>

          <a
            href={templateUrl}
            download="products_template.csv"
            className="inline-flex items-center gap-2 text-sm text-primary hover:underline"
          >
            <Download className="size-4" />
            Download template
          </a>
        </CardContent>
      </Card>

      {preview.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Preview (first 5 rows)</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>name</TableHead>
                  <TableHead>sku</TableHead>
                  <TableHead>price</TableHead>
                  <TableHead>url</TableHead>
                  <TableHead>category</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {preview.map((row, i) => (
                  <TableRow key={i}>
                    <TableCell>{row.name}</TableCell>
                    <TableCell>{row.sku}</TableCell>
                    <TableCell>{row.price}</TableCell>
                    <TableCell className="max-w-32 truncate">{row.url}</TableCell>
                    <TableCell>{row.category}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {previewErrors.length > 0 && (
              <p className="mt-2 text-sm text-destructive">
                Errors: {previewErrors.map((e) => `Row ${e.row}: ${e.message}`).join("; ")}
              </p>
            )}
            <Button
              className="mt-4"
              onClick={handleImport}
              disabled={importing || previewErrors.length > 0}
            >
              {importing ? "Importing..." : "Import"}
            </Button>
          </CardContent>
        </Card>
      )}

      {result && (
        <Card>
          <CardHeader>
            <CardTitle>Result</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="font-medium">
              Imported: {result.imported} · Errors: {result.errors.length}
            </p>
            {result.errors.length > 0 && (
              <ul className="mt-2 list-inside list-disc text-sm text-destructive">
                {result.errors.map((e, i) => (
                  <li key={i}>
                    Row {e.row}: {e.message}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
