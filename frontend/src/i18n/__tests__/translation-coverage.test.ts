import { readdir, readFile, stat } from "node:fs/promises";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  flattenTranslationKeys,
  type TranslationResourceMap,
} from "../translationGuard";

const FRONTEND_ROOT = path.resolve(process.cwd());
const LOCALES_ROOT = path.join(FRONTEND_ROOT, "public", "locales");
const SOURCE_ROOT = path.join(FRONTEND_ROOT, "src");

const SUPPORTED_LANGUAGE_CODES = ["en", "ar", "es", "zh", "ru", "fr", "ro", "uk"] as const;
const PUBLIC_LANGUAGE_CODES = SUPPORTED_LANGUAGE_CODES.filter((code) => code !== "ru");
const TARGET_SOURCE_DIRS = ["pages", "components", "hooks", "lib"];

interface KeyUsage {
  key: string;
  filePath: string;
}

interface HardcodedViolation {
  filePath: string;
  text: string;
}

interface CyrillicViolation {
  filePath: string;
  lineNumber: number;
  line: string;
}

async function listFilesRecursive(directoryPath: string): Promise<string[]> {
  const entries = await readdir(directoryPath, { withFileTypes: true });
  const files: string[] = [];

  for (const entry of entries) {
    const absolutePath = path.join(directoryPath, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await listFilesRecursive(absolutePath)));
      continue;
    }
    files.push(absolutePath);
  }

  return files;
}

async function loadLocaleResources(): Promise<TranslationResourceMap> {
  const resources: TranslationResourceMap = {};

  for (const code of SUPPORTED_LANGUAGE_CODES) {
    const localePath = path.join(LOCALES_ROOT, code, "translation.json");
    const raw = await readFile(localePath, "utf-8");
    resources[code] = JSON.parse(raw) as Record<string, unknown>;
  }

  return resources;
}

function collectTranslationKeyUsage(filePath: string, source: string): KeyUsage[] {
  const usages: KeyUsage[] = [];
  const regex = /\b(?:t|i18n\.t)\(\s*["'`]([^"'`]+)["'`]/g;

  for (const match of source.matchAll(regex)) {
    const key = match[1]?.trim();
    if (!key) continue;
    usages.push({ key, filePath });
  }

  return usages;
}

function collectHardcodedTextNodes(filePath: string, source: string): HardcodedViolation[] {
  const violations: HardcodedViolation[] = [];
  const textNodeRegex = />\s*([^<>{\n][^<>{\n]*[A-Za-zА-Яа-я][^<>{\n]*)\s*</g;

  for (const match of source.matchAll(textNodeRegex)) {
    const text = match[1]?.trim() ?? "";
    if (!text) continue;
    if (text.includes("{") || text.includes("}")) continue;
    if (text.length < 2) continue;
    if (/^[0-9:%./+-]+$/.test(text)) continue;
    if (/^[A-Z_]+$/.test(text)) continue;
    if (/^https?:\/\//.test(text)) continue;
    if (/^#[A-Za-z0-9_-]+$/.test(text)) continue;
    violations.push({ filePath, text });
  }

  return violations;
}

describe("translation coverage diagnostics", () => {
  it("loads translation resources for every supported language", async () => {
    const resources = await loadLocaleResources();
    expect(Object.keys(resources).sort()).toEqual([...SUPPORTED_LANGUAGE_CODES].sort());
  });

  it("checks that every t()/i18n.t() key exists in all public languages", async () => {
    const resources = await loadLocaleResources();
    const publicKeySets = Object.fromEntries(
      PUBLIC_LANGUAGE_CODES.map((code) => [code, flattenTranslationKeys(resources[code])]),
    ) as Record<string, Set<string>>;

    const sourceFiles: string[] = [];
    for (const directory of TARGET_SOURCE_DIRS) {
      const absolute = path.join(SOURCE_ROOT, directory);
      if (!(await stat(absolute).catch(() => null))) continue;
      const files = await listFilesRecursive(absolute);
      sourceFiles.push(
        ...files.filter((file) => /\.(ts|tsx)$/.test(file) && !/\.test\.(ts|tsx)$/.test(file)),
      );
    }

    const missingUsageDiagnostics: string[] = [];
    for (const filePath of sourceFiles) {
      const source = await readFile(filePath, "utf-8");
      const usages = collectTranslationKeyUsage(filePath, source);
      for (const usage of usages) {
        for (const code of PUBLIC_LANGUAGE_CODES) {
          if (!publicKeySets[code].has(usage.key)) {
            const relative = path.relative(FRONTEND_ROOT, usage.filePath);
            missingUsageDiagnostics.push(
              `${relative}: key "${usage.key}" missing in locale "${code}"`,
            );
          }
        }
      }
    }

    expect(
      missingUsageDiagnostics,
      `Translation key usage gaps:\n${missingUsageDiagnostics.slice(0, 60).join("\n")}`,
    ).toEqual([]);
  });

  it("fails on hardcoded Cyrillic UI text outside locales", async () => {
    const violations: CyrillicViolation[] = [];
    const scanDirs = ["pages", "components"];

    for (const directory of scanDirs) {
      const absolute = path.join(SOURCE_ROOT, directory);
      if (!(await stat(absolute).catch(() => null))) continue;
      const files = await listFilesRecursive(absolute);
      const tsxFiles = files.filter((file) => file.endsWith(".tsx") && !file.endsWith(".test.tsx"));

      for (const filePath of tsxFiles) {
        const source = await readFile(filePath, "utf-8");
        const lines = source.split(/\r?\n/);
        lines.forEach((line, index) => {
          if (!/[А-Яа-яЁё]/.test(line)) return;

          violations.push({
            filePath,
            lineNumber: index + 1,
            line: line.trim(),
          });
        });
      }
    }

    const preview = violations
      .slice(0, 80)
      .map((item) => `${path.relative(FRONTEND_ROOT, item.filePath)}:${item.lineNumber} ${item.line}`);

    expect(
      violations,
      `Hardcoded non-English UI text detected:\n${preview.join("\n")}`,
    ).toEqual([]);
  });

  it("provides diagnostics for hardcoded UI text nodes", async () => {
    const diagnostics: HardcodedViolation[] = [];
    const scanDirs = ["pages", "components"];

    for (const directory of scanDirs) {
      const absolute = path.join(SOURCE_ROOT, directory);
      if (!(await stat(absolute).catch(() => null))) continue;
      const files = await listFilesRecursive(absolute);
      const tsxFiles = files.filter((file) => file.endsWith(".tsx"));

      for (const filePath of tsxFiles) {
        const source = await readFile(filePath, "utf-8");
        diagnostics.push(...collectHardcodedTextNodes(filePath, source));
      }
    }

    const preview = diagnostics
      .slice(0, 80)
      .map((item) => `${path.relative(FRONTEND_ROOT, item.filePath)}: "${item.text}"`);

    if (diagnostics.length > 0) {
      console.warn(
        `[i18n-diagnostics] Hardcoded UI text nodes detected (${diagnostics.length}).\n${preview.join("\n")}`,
      );
    }

    expect(diagnostics.length).toBeGreaterThanOrEqual(0);
  });
});

