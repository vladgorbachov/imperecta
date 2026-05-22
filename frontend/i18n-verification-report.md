# i18n Verification Report

## Coverage status by language

| Language | Locale | Total keys | Missing vs `en` | Public access | Status |
|---|---:|---:|---:|---|---|
| English | `en` | 728 | 0 | Yes | Baseline |
| Arabic | `ar` | 700 | 38 | Yes | Needs completion |
| Spanish | `es` | 700 | 38 | Yes | Needs completion |
| Chinese | `zh` | 700 | 38 | Yes | Needs completion |
| French | `fr` | 700 | 38 | Yes | Needs completion |
| Romanian | `ro` | 707 | 31 | Yes | Needs completion |
| Ukrainian | `uk` | 722 | 6 | Yes | Needs completion |
| Russian | `ru` | 719 | 9 | Admin-only | Restricted |

Notes:
- Public runtime checks now enforce key usage coverage across public languages (non-admin locales).
- Russian remains in supported languages but is hidden for non-admin users.

## Found issues with file paths

### Missing key families (global locale parity vs `en`)
- Country labels missing in several public locales:
  - Prefix: `countries.*`
  - Affected locales: `ar`, `es`, `zh`, `fr`, partly `ro`, `uk`
- Additional sparse gaps in non-public-critical namespaces remain and should be filled incrementally.

### Hardcoded UI text diagnostics
- Current diagnostics detected **114 hardcoded UI text nodes**.
- Main hotspots:
  - `src/pages/AdminPage.tsx`
  - `src/pages/landing/LandingPage.tsx`
  - `src/components/dashboard/MarketDataTable.tsx`
  - `src/components/dashboard/MarketsAnalyticsSection.tsx`
  - `src/pages/ProductsPage.tsx`
  - `src/pages/ImportPage.tsx`

These are reported by `translation-coverage.test.ts` with file-level details to support incremental cleanup.

## Translation Control Module status

Module: `src/i18n/translationGuard.ts`

Implemented:
- Central policy function for role-based language exposure:
  - `getLanguagesForUser()` (RU admin-only).
- Translation key utilities:
  - `flattenTranslationKeys()`
  - `validateTranslationCoverage()`
  - `findMissingLanguagesForKey()`
  - `assertTranslationKey()`
  - `useTranslationGuard()` hook for component-level registration in dev mode.
- i18n integration in `src/i18n/index.ts`:
  - `PUBLIC_LANGUAGES`, `PUBLIC_LANGUAGE_CODES`
  - `getAvailableLanguages(isAdmin)`
  - `enforceLanguagePolicy(isAdmin)` with persisted-language handling.
  - Dev-only translation audit entrypoint (`runTranslationCoverageAudit`).

## Test status

Command:
- `npx vitest run src/i18n/__tests__`

Result:
- **3 test files passed**
- **14 tests passed**

Test suites:
- `guard.test.ts` (unit)
- `language-access.test.tsx` (language policy / admin restriction)
- `translation-coverage.test.ts` (integration coverage + diagnostics)

Additional checks:
- `npx eslint` on modified i18n/language files: no errors (security warnings only).
- `npx tsc --noEmit`: failed due pre-existing unrelated syntax errors in:
  - `src/components/products/MyProductsTab.tsx`
  - `src/components/products/PoolProductsTab.tsx`

## Recommendations for maintaining 100% coverage

1. **Complete locale parity**
   - Fill all remaining `missing_vs_en` keys for public locales (`ar`, `es`, `zh`, `fr`, `ro`, `uk`), starting with `countries.*`.
2. **Eliminate hardcoded UI text**
   - Convert each diagnostic string to `t("...")` keys and add translations in all public locales.
3. **Keep RU restricted**
   - Continue using `getAvailableLanguages(isAdmin)` and `enforceLanguagePolicy(isAdmin)` in all language-switch entry points.
4. **CI integration**
   - Add `npx vitest run src/i18n/__tests__` as required CI gate before merge/deploy.
5. **Future components**
   - Use `useTranslationGuard([...keys], resources, PUBLIC_LANGUAGE_CODES)` in new UI components during development.

