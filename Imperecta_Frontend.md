# Imperecta — Frontend

**Актуально на:** 2026-06-07 (head `4d42623`)  
**Стек:** React 19, TypeScript strict, Vite 6, React Router 7, TanStack Query 5, Tailwind 4, Radix/shadcn, Zustand, i18next, axios, framer-motion, recharts, sonner.

---

## 1. Структура

```
frontend/src/
├── main.tsx           # setupAuth, i18n, AppWithInit
├── App.tsx            # routes, providers
├── api/               # axios clients
├── hooks/             # React Query
├── stores/authStore.ts
├── components/        # feature + ui
├── pages/
├── i18n/
└── lib/routes.ts
```

**Env:** `VITE_API_URL` (обязателен) → `apiBaseUrl = ${url}/api`.

**Деплой:** Cloudflare Pages, `npm run build`.

---

## 2. Bootstrap

**`main.tsx`:** `setupAuth` → `i18n` → `AppWithInit` (session restore) → `App`.

**Providers:** QueryClient → AuthProvider → ThemeProvider (dark default) → Tooltip → Suspense → Router → Toaster (sonner: glass + `imperecta-sonner-*` classes; centered layout overrides in `styles/components.css`).

---

## 3. Маршруты (`App.tsx`)

### Публичные

| Path | Guard | Page |
|------|-------|------|
| `/ai.market.intelligence.agent` | `LandingRoute` | `LandingPage` |
| `/login`, `/register`, `/forgot-password` | `PublicAuthRoute` | auth |
| `/change-password` | `ChangePasswordRoute` | force password |
| `*` | — | `NotFoundPage` |

### Protected + `DashboardLayout`

| Path | Page |
|------|------|
| `/` → `/dashboard` | redirect |
| `/dashboard` | `DashboardPage` |
| `/products`, `/products/:id` | products |
| `/digests` | `DigestsPage` |
| `/import` | `ImportPage` |
| `/analytics` | `AnalyticsPage` |
| `/ai` | `AIAnalystRoute` → `AIAnalystPage` |
| `/settings` | `SettingsPage` |

### Admin (superuser)

| Path | Page |
|------|------|
| `/admin` | `AdminPage` (index) |

### Без route (legacy / WIP)

- `CompetitorsPage.tsx`, `AlertsPage.tsx` — clients есть, routes нет.
- `AiPage.tsx` — заменён `AIAnalystPage`.

---

## 4. Layout

**`DashboardLayout`:** sidebar + header + scroll `main` + `Outlet`; motion on path change; `MobileSidebar`, `BottomNavigation`, `SessionExpiryWarning`.

**Навигация:** Dashboard, Products, Digests, Import, Analytics, AI (entitlement), Admin (superuser). Settings — из Header.

**Sidebar collapse:** `useSidebar` → `localStorage` `imperecta_sidebar_collapsed`.

---

## 5. API layer

### `client.ts`

- HTTPS page → force `https://` API URL.
- `apiClient` axios, `baseURL: apiBaseUrl`.

### `setupAuth.ts`

- Bearer from `authStore` / `authStorage`.
- 401 → single refresh attempt → retry or logout.

### Модули

| File | Paths |
|------|-------|
| `auth.ts` | `/auth/*` |
| `products.ts` | `/products`, `/pool/*` |
| `markets.ts` | `/markets/*`, ingest |
| `competitors.ts`, `alerts.ts` | есть; backend alerts router off |
| `analytics.ts`, `digests.ts`, `import.ts`, `ai.ts` | domain APIs |
| `admin.ts` | `/admin/*`, `/admin/parsing/*` |

### Admin parsing types (`admin.ts`)

- `RunPipelinePayload`: optional `marketplace_codes[]`
- `ParsingJobStatus`, `ParsingLiveStep`, `ParsingPipelineRun`
- `getParsingWorkerLogRelay(after, jobId, limit)`
- User CRUD request/response types

---

## 6. Hooks (`useAdmin.ts` и др.)

### Parsing / Data Collection

| Hook | Interval / notes |
|------|------------------|
| `useRunParsingPipeline` | mutation |
| `useCancelParsingActiveJob` | mutation |
| `useParsingActiveJob` | ~4–5s |
| `useParsingJobStatus` | 2s when monitoring |
| `useParsingJobLiveFeed` | 3s during scrape |
| `useParsingWorkerLogRelay` | 2s, cursor `after` |
| `useParsingPipelineRuns(limit)` | 5s; default limit **10** в UI |
| `useParsingTestMarketplaces` | marketplace cards |

### Users Management

| Hook | Notes |
|------|-------|
| `useParsingUsersDetailed(limit)` | default 500 |
| `useCreateAdminUser` | POST |
| `useUpdateAdminUser` | PATCH profile/plan |
| `useSetAdminUserStatus` | active flag |
| `useSetAdminUserRole` | superuser |
| `useResetAdminUserPassword` | POST |
| `useDeleteAdminUser` | DELETE |

### Market Overview

| Hook | Notes |
|------|-------|
| `useAdminStats`, `useClaudeStatus` | 60s poll Claude |
| `useAddMarketplace`, `useUpdateMarketplace`, `useDeleteMarketplace` | |
| `useMarketsIngest` | trigger ingestion |
| `useParsingMarketplacesDetailed` | paginated API |

Другие: `useAuth`, `useProducts`, `usePoolProducts` (передают `display_currency`), `useDisplayCurrency`, `useEntitlements`, `usePlanLimits`.

---

## 7. Display currency

| Файл | Роль |
|------|------|
| `lib/displayCurrency.ts` | Modes `local` \| `EUR` \| `USD`; `resolvePriceForDisplay`; storage key |
| `lib/marketplaceLabel.ts` | `formatMarketplaceLabel` — country suffix for local TLD stores |
| `hooks/useMarketplaceLabel.ts` | Locale-aware formatter hook |
| `stores/displayCurrencyStore.ts` | Zustand — выбранная валюта |
| `hooks/useDisplayCurrency.ts` | Форматирование, `apiParam` для запросов |
| `components/ui/DisplayCurrencySelector.tsx` | Переключатель в Header / Markets |
| `components/ui-custom/PriceDisplay.tsx` | Цена + badge `noRate` при отсутствии курса |

**Поток:** UI → `?display_currency=EUR|USD|local` → backend `CurrencyConverter` + `marketplace_locale` → `display_price`, `conversion_available`, `local_currency_resolution`, `local_currency_unavailable`.

**Режим `local`:** backend резолвит валюту по TLD домена; при `local_currency_unavailable` — `MarketsOverviewSection` отключает local toggle.

**Формат цен (`c8f464b`):** `formatPrice` в `lib/formatters.ts` — всегда `minimumFractionDigits: 2`.

**Используется в:** `MyProductsTab`, `PoolProductsTab`, `ProductDetailPage`, `CompetitorsPage`, `MarketsOverviewSection`, `MarketsAnalyticsSection`, analytics hooks.

---

## 8. Dashboard — Markets product catalog (`7f16333`)

**`MarketsOverviewSection.tsx`** на `/dashboard`:

- Каталог товаров из `/markets/overview` (не admin marketplaces table).
- Поиск, фильтры, сортировка: recent, gainers, losers, volatile, trending.
- Пагинация: `PAGE_LIMIT=200`, progressive expand (+20).
- `DisplayCurrencySelector` + `PriceDisplay` с converted prices.
- Добавление в user products (`productsApi`).

Отдельно: **Admin → Market Overview** — CRUD marketplaces, ingest (см. §9).

---

## 9. State

| Concern | Solution |
|---------|----------|
| Auth | Zustand `authStore` |
| Display currency | Zustand `displayCurrencyStore` |
| Server | TanStack Query |
| Theme | next-themes |
| UI local | `useState` in pages |

---

## 10. i18n

- **8 locales:** en, ar, es, zh, ru, fr, ro, uk — `public/locales/{lng}/translation.json`
- **Storage:** `imperecta_language`
- **Russian:** только superuser (`enforceLanguagePolicy`)
- **RTL:** `ar`
- **Guard/audit:** `translationGuard.ts`, dev coverage audit
- **`App.tsx`:** большой comment-index ключей по namespace

---

## 11. Admin UI (`AdminPage.tsx`)

Монолит ~1300 строк с тремя табами.

### Tab: Market Overview

- Admin stats cards, Claude status.
- Marketplaces table: search, pagination **20 / 50 / 100** (`MARKET_OVERVIEW_PAGE_SIZE_OPTIONS`).
- Add/update/delete marketplace, trigger markets ingest.

### Tab: Data Collection

Компонент **`DataCollectionTab.tsx`** (redesign):

**Запуск:**

- Full pipeline — все active marketplaces.
- Scoped — чекбоксы + `marketplace_codes` в payload; backend применяет тот же filter на **discovery и scrape** (не только discovery).
- Кнопки disabled при active job; **Cancel** → `useCancelParsingActiveJob`.
- **Clear selection** для marketplace picker.

**Live monitor** (running job):

| UI | Data |
|----|------|
| Stage progress | dispatching → discovery → scrape → persist |
| Stale badge | `last_activity_at` > **300s** (`STALE_ACTIVITY_SECONDS`) |
| Metrics cards | listings, prices, errors, elapsed |
| Tabs Discovery / Scrape / Summary | status, per-MP table, recharts pie/bar/timeline |
| `WorkerLogRelayPanel` | только `status === "running"` |

**History:**

- `RUNS_LIMIT = 10` pipeline runs (не 200).
- Resizable columns (`RUN_HISTORY_COLUMNS`: job, date, scope, stage, products, prices, errors, status, error).
- Row click → monitor + details dialog (`onOpenRunDetails`).

### Tab: Users Management

- Table + search/filter.
- Dialogs: create user, edit profile, reset password, toggle active/superuser, delete.
- **Plans:** trial, starter, business, pro, enterprise.
- **Languages:** все 8 кодов в форме (superuser может назначить ru).

---

## 12. `WorkerLogRelayPanel.tsx`

- `useParsingWorkerLogRelay({ jobId, after, enabled })` — refetch **2s**.
- Cursor: `after` / `next_cursor` from API.
- Client buffer до **120** строк; API returns `visible_lines: 3`.
- Mono terminal style (emerald on dark).
- `aria-live="polite"`.
- Reset when `!enabled || !jobId`.

---

## 13. Products UI

- **`MyProductsTab` / `PoolProductsTab`:** pagination 20/50/100, row selection, bulk delete.
- **`ProductDetailPage`:** charts, run parsing action.
- Plan limits: `PlanLimitBanner`, `usePlanLimits`.

---

## 14. Entitlements (client)

- `useEntitlements` — feature flags from user/plan.
- `AIAnalystRoute` — блок без PAID_FULL + AI feature.
- Trial: full platform кроме AI (соответствует backend `ServiceTier.TRIAL`).

---

## 15. Безопасность

- JWT storage abstraction (`authStorage`).
- DOMPurify для AI markdown.
- ESLint security plugin.
- No secrets in `VITE_*` except public API URL.

---

## 16. Тесты

- **Vitest:** `cd frontend && npm test`
- `AdminPage.parsing.test.tsx`, `MarketsOverviewSection.test.tsx`, `marketplaceLabel.test.ts`
- i18n tests under `src/i18n/__tests__/`
- **Playwright E2E:** `e2e/` — smoke против Cloudflare/Railway URL в CI
- **Backend pytest:** см. `Imperecta_Backend.md` §12 — требует `backend/.env` + Postgres `imperecta_test`

---

## 17. Универсальность UI

- Нет store-specific labels в i18n (удалены named marketplace strings в `1f024b1`).
- Data Collection и Market Overview работают с любыми `dim_marketplace` по `code` / URL, без hardcoded доменов во фронте.
- Pipeline test: scoped run через `marketplace_codes[]` — без привязки к конкретному ритейлеру в UI.

**`scrape_tier`:** поле есть в БД и backend (`e286053`), **UI для редактирования tier пока нет** — назначение tier через SQL/admin API в будущем.

---

## 18. Известные расхождения

| Тема | Состояние |
|------|-----------|
| `/competitors`, `/alerts` | Pages + API clients; no routes |
| Backend `/api/alerts` | Router not in main |
| Sidebar i18n keys for competitors/alerts | Legacy comments in App.tsx |

---

## 20. Детальная логика элементов

### 20.1 Bootstrap chain (`main.tsx`)

1. `setupAuth()` — attach axios interceptors before any API call.
2. Load i18n resources.
3. `AppWithInit` — restore session from storage, validate token.
4. Render `App` with QueryClient + providers.

---

### 20.2 Auth flow

| Элемент | Логика |
|---------|--------|
| `authStore` | Zustand: user, tokens, login/logout actions |
| `authStorage` | Abstraction over localStorage keys |
| `setupAuth.ts` | Inject Bearer; on 401 → refresh once → retry or logout |
| Route guards | `ProtectedRoute`, `AdminRoute`, `AIAnalystRoute`, `LandingRoute` |

---

### 20.3 Display currency stack

| Элемент | Логика |
|---------|--------|
| `displayCurrencyStore` | Persist mode `local` \| `EUR` \| `USD` |
| `useDisplayCurrency` | Expose `apiParam` for query string |
| `DisplayCurrencySelector` | UI toggle; writes store |
| `PriceDisplay` | Render via `formatPrice` (2 decimals); badge when `!conversion_available` |
| API types | `local_currency_resolution`, `local_currency_unavailable` on pool/products/markets |
| API consumers | Append `?display_currency=` on products/pool/dashboard requests |

**Правило:** конвертация и local-currency resolution только на backend.

### 20.3b Marketplace labels

| Элемент | Логика |
|---------|--------|
| `formatMarketplaceLabel` | Base name; append `(Country)` for country-TLD domains |
| `isInternationalMarketplace` | Known globals (amazon.com, ebay.com, …) and generic .com → no suffix |
| `useMarketplaceLabelFormatter` | Binds current i18n locale for country names (ru uses `name_local`) |
| Consumers | `MarketsOverviewSection`, `PoolProductsTab`, `MarketsAnalyticsSection`, `MarketplaceBadge` |

---

### 20.4 Admin parsing hooks (`useAdmin.ts`)

| Hook | Логика |
|------|--------|
| `useRunParsingPipeline` | POST `/run-pipeline` with optional `marketplace_codes`; invalidate active job |
| `useCancelParsingActiveJob` | POST cancel; stop polls |
| `useParsingActiveJob` | ~4s poll while admin tab open |
| `useParsingJobStatus(jobId)` | 2s when monitoring selected job |
| `useParsingJobLiveFeed` | 3s — steps from `scrape_logs` aggregation |
| `useParsingWorkerLogRelay` | 2s; cursor `after` from `next_cursor`; filter by `jobId` |
| `useParsingPipelineRuns(10)` | History table data |

---

### 20.5 `DataCollectionTab.tsx`

| UI block | Логика |
|----------|--------|
| **Marketplace picker** | Checkboxes → scoped `marketplace_codes`; Clear selection |
| **Run buttons** | Disabled when `useParsingActiveJob` returns running job |
| **Cancel** | Calls cancel mutation; expects parent failed server-side |
| **Stage progress** | Maps `metadata.current_stage`: dispatching → discovery → scrape → persist |
| **Stale badge** | If `now - last_activity_at > 300s` (`STALE_ACTIVITY_SECONDS`) — warning only (server stale at 30 min) |
| **Metrics cards** | From `metadata.summary` + elapsed timer |
| **Charts** | Recharts pie (scrape status), bar per MP, timeline throughput |
| **History** | `RUNS_LIMIT=10`; resizable columns; row click opens monitor |
| **WorkerLogRelayPanel** | Enabled only when `status === "running"` |

---

### 20.6 `WorkerLogRelayPanel.tsx`

1. `useParsingWorkerLogRelay({ jobId, after, enabled })`.
2. Append new lines to client buffer (max 120).
3. Reset buffer when jobId changes or disabled.
4. Mono terminal styling; `aria-live="polite"`.

---

### 20.7 `MarketsOverviewSection.tsx`

| Feature | Логика |
|---------|--------|
| Data source | `GET /markets/overview` (dashboard API) |
| Search/filter | Client-side on product name/code |
| Sort modes | recent, gainers, losers, volatile, trending |
| Pagination | `PAGE_LIMIT=200`; expand +20 |
| Currency | `DisplayCurrencySelector` + `PriceDisplay` per row |
| Marketplace label | `useMarketplaceLabelFormatter()` — country suffix for local TLD |
| Local currency guard | Disable local when `local_currency_unavailable` or `source === "unknown"` |
| Add to catalog | `productsApi` create from pool item |

---

### 20.8 `AdminPage.tsx` — три таба

| Tab | Логика |
|-----|--------|
| **Market Overview** | Stats cards; marketplaces CRUD paginated 20/50/100; ingest trigger |
| **Data Collection** | Delegates to `DataCollectionTab` |
| **Users Management** | Table + dialogs; plans trial→enterprise; languages all 8 |

---

### 20.9 API clients (`api/`)

| Client | Логика |
|--------|--------|
| `client.ts` | Force HTTPS when page is HTTPS |
| `admin.ts` | Parsing + user admin types and endpoints |
| `products.ts` | User products + pool with display_currency |
| `markets.ts` | Market widgets + overview |

---

### 20.10 Entitlements (client)

`useEntitlements` reads user plan → feature flags. `AIAnalystRoute` blocks render without PAID_FULL + AI feature. Trial: full platform except AI.

---

## 21. Источники

| Область | Путь |
|---------|------|
| Routes | `frontend/src/App.tsx` |
| Admin page | `frontend/src/pages/AdminPage.tsx` |
| Data Collection | `frontend/src/components/admin/DataCollectionTab.tsx` |
| Worker logs | `frontend/src/components/admin/WorkerLogRelayPanel.tsx` |
| Admin API | `frontend/src/api/admin.ts` |
| Hooks | `frontend/src/hooks/useAdmin.ts` |
| Auth | `frontend/src/stores/authStore.ts` |
| Marketplace labels | `frontend/src/lib/marketplaceLabel.ts`, `hooks/useMarketplaceLabel.ts` |

Связанные документы: `Imperecta_Architecture.md`, `Imperecta_Backend.md`, `Imperecta_Parsing.md`.
