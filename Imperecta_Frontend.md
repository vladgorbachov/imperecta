# Imperecta — Frontend (детальное описание)

**Актуально на:** 2026-05-28  
**Стек:** React 19, TypeScript (strict), Vite 6, React Router 7, TanStack Query 5, Tailwind CSS 4, shadcn/ui (Radix), Zustand, i18next, axios, framer-motion, recharts.

---

## 1. Структура проекта

```
frontend/
├── public/locales/{en,ar,es,zh,ru,fr,ro,uk}/translation.json
├── src/
│   ├── main.tsx              # AppWithInit, i18n, setupAuth
│   ├── App.tsx               # routes, providers
│   ├── api/                  # HTTP clients per domain
│   ├── hooks/                # React Query wrappers
│   ├── stores/               # authStore (Zustand)
│   ├── components/           # UI by feature
│   ├── pages/                # route pages
│   ├── i18n/                 # init, guard, audit
│   └── lib/                  # routes, utils, entitlements helpers
├── package.json
└── vite.config.ts
```

**Сборка:** `npm run build` → статика для Cloudflare Pages.  
**Env:** `VITE_API_URL` — обязательный базовый URL backend (без `/api` suffix в env; клиент добавляет `/api`).

---

## 2. Bootstrap и провайдеры

**`main.tsx`:**

1. Импорт `@/api/setupAuth` (interceptors).
2. Импорт `@/i18n`.
3. `AppWithInit` — восстановление сессии из storage до рендера защищённых маршрутов.
4. `App` — роутинг.

**`App.tsx` провайдеры (снаружи внутрь):**

- `QueryClientProvider` — default staleTime, retry policy.
- `AuthProvider` — контекст поверх Zustand.
- `ThemeProvider` (next-themes) — default dark.
- `TooltipProvider`
- `Suspense` + `BrowserRouter`
- `Toaster` (sonner)

---

## 3. Маршрутизация

**Файл:** `src/App.tsx`  
**Политика путей:** `src/lib/routes.ts` (`PUBLIC_ROUTES`, `LANDING_PATH`, `getLoginUrl`).

### 3.1 Публичные маршруты

| Path | Guard | Page |
|------|-------|------|
| `/ai.market.intelligence.agent` | `LandingRoute` | `LandingPage` |
| `/login`, `/register`, `/forgot-password` | `PublicAuthRoute` | auth pages |
| `/change-password` | `ChangePasswordRoute` | `ForcePasswordChangePage` |
| `*` | — | `NotFoundPage` |

`LandingRoute`: если есть токен → redirect `/dashboard`.

### 3.2 Защищённое приложение

`ProtectedRoute` + `DashboardLayout` (`<Outlet />`):

| Path | Page |
|------|------|
| `/` | redirect → `/dashboard` |
| `/dashboard` | `DashboardPage` |
| `/products`, `/products/:id` | `ProductsPage`, `ProductDetailPage` |
| `/digests` | `DigestsPage` |
| `/import` | `ImportPage` |
| `/analytics` | `AnalyticsPage` |
| `/ai` | `AIAnalystRoute` → `AIAnalystPage` |
| `/settings` | `SettingsPage` |

### 3.3 Admin

| Path | Guard | Page |
|------|-------|------|
| `/admin` | `SuperuserRoute` + `DashboardLayout` | `AdminPage` |

### 3.4 Страницы без маршрута (WIP / legacy)

- `CompetitorsPage.tsx` — API client есть, route **нет**.
- `AlertsPage.tsx` — аналогично.
- `AiPage.tsx` — заменён `AIAnalystPage`.

---

## 4. Layout и навигация

### `DashboardLayout`

- Grid: sidebar + header + scrollable `main`.
- `framer-motion` — анимация при смене pathname.
- `MobileSidebar`, `BottomNavigation` — responsive.
- `SessionExpiryWarning` — предупреждение об истечении refresh.

### Sidebar / Header

- Основные пункты: Dashboard, Products, Digests, Import, Analytics, AI (с entitlement), Admin (superuser).
- Settings — из `Header`, не в sidebar.
- Collapse state: `useSidebar` → localStorage `imperecta_sidebar_collapsed`.

---

## 5. API layer (`src/api/`)

### 5.1 `client.ts`

```typescript
apiBaseUrl = `${normalizedViteApiUrl}/api`
```

- На HTTPS-странице `http://` API URL принудительно → `https://`.
- `apiClient` — axios instance.

### 5.2 `setupAuth.ts`

- Request: `Authorization: Bearer ${accessToken}` из `authStore` / `authStorage`.
- Response 401: один coordinated refresh, retry original request или logout.

### 5.3 Модули

| Файл | Endpoints (relative to `/api`) |
|------|--------------------------------|
| `auth.ts` | `/auth/*` |
| `products.ts` | `/products`, `/pool/*` |
| `markets.ts` | `/markets/*`, ingest |
| `competitors.ts` | `/competitors/*` |
| `alerts.ts` | `/alerts`, `/alerts/events` |
| `analytics.ts` | `/analytics/*` |
| `digests.ts` | `/digests` |
| `import.ts` | `/import/products/*` |
| `ai.ts` | `/ai/*` |
| `admin.ts` | `/admin/*`, `/admin/parsing/*` |

### 5.4 Admin parsing API (`admin.ts`)

Типы и функции для:

- `getParsingTestMarketplaces`
- `runParsingPipeline` → `POST /admin/parsing/run-pipeline`
- `cancelParsingActiveJob`
- `getParsingPipelineRuns`, `getParsingJobStatus`, `getParsingJobLiveFeed`
- `getParsingWorkerLogRelay(after, jobId, limit)`
- `getParsingActiveJob`
- Users CRUD under `/admin/parsing/users*`
- `getParsingMarketplacesDetailed`

---

## 6. Hooks (React Query)

**Паттерн:** один hook = query/mutation + cache keys `["domain", "sub", ...]`.

### `useAdmin.ts` (ключевой для admin)

| Hook | Poll / notes |
|------|----------------|
| `useAdminStats` | admin overview |
| `useClaudeStatus` | 60s |
| `useRunParsingPipeline` | mutation |
| `useCancelParsingActiveJob` | mutation |
| `useParsingPipelineRuns` | 5s when monitoring |
| `useParsingJobStatus(jobId)` | 2s when active |
| `useParsingJobLiveFeed(jobId)` | 3s during scrape |
| `useParsingWorkerLogRelay` | 2s, cursor `after` |
| `useParsingActiveJob` | 4–5s |
| `useParsingUsersDetailed` + mutations | user admin |
| `useParsingMarketplacesDetailed` | marketplace picker |
| `useParsingTestMarketplaces` | test cards |

Другие hooks: `useAuth`, `useProducts`, `usePoolProducts`, `useCompetitors`, `useAlerts`, `useAnalytics`, `useEntitlements`, `usePlanLimits`, `useDebounce`, `useRowSelection`.

---

## 7. State management

| Тип | Реализация |
|-----|------------|
| Auth | **Zustand** `stores/authStore.ts` — user, tokens, login/logout/refresh, language policy |
| Server state | TanStack Query |
| UI local | `useState` в компонентах |
| Theme | next-themes |
| Sidebar | localStorage via `useSidebar` |

**Нет** глобального store для products/parsing — только Query cache.

---

## 8. i18n

**Инициализация:** `src/i18n/index.ts`

- i18next + react-i18next + http-backend + languageDetector (отключены в Vitest).
- Файлы: `public/locales/{lng}/translation.json`.
- Storage key: `imperecta_language`.
- **8 языков:** en, ar, es, zh, ru, fr, ro, uk.
- **Русский:** доступен только superuser (`enforceLanguagePolicy`, `getAvailableLanguages`).
- **RTL:** `ar` → `document.documentElement.dir = 'rtl'`.
- **Guard:** `translationGuard.ts`, dev audit `runTranslationCoverageAudit`.

UI: `LanguageSelector`, `useTranslation()` повсеместно.

---

## 9. Admin UI

### 9.1 `AdminPage.tsx`

Tabs:

1. **Market Overview** — stats, Claude status, marketplaces ingest.
2. **Data Collection** — `DataCollectionTab`.
3. **Users Management** — parsing users table + dialogs.

Диалог деталей pipeline run — открывается из Data Collection (`onOpenRunDetails`).

### 9.2 `DataCollectionTab.tsx`

**Запуск pipeline:**

- Full pool: `runPipeline.mutateAsync(undefined)`.
- Scoped: `{ marketplace_codes: [...] }` из чекбоксов active marketplaces.
- Блокировка при `activeJobId`; cancel через `useCancelParsingActiveJob`.

**Live monitor** (когда есть active/running job):

| Элемент | Источник |
|---------|----------|
| Progress bar | `job-status` → stage |
| Stale warning | `last_activity_at` > 300s |
| Metrics | listings, prices, errors, elapsed, scrape steps |
| Tab Discovery | scope, celery_task_id, per-marketplace table |
| Tab Scrape | pie по статусам, bar chart, throughput timeline |
| Tab Summary | timings, error, link to details |
| WorkerLogRelayPanel | только `status === "running"` |

**История:** до 200 runs, pagination 20, click → monitor + details dialog.

### 9.3 `WorkerLogRelayPanel.tsx`

- `useParsingWorkerLogRelay({ jobId, after, enabled })` — refetch 2s.
- Cursor pagination: `after` / `next_cursor`.
- Buffer до 120 строк, display 3 (terminal mono emerald).
- Reset при `!enabled || !jobId`.
- `aria-live="polite"`.

---

## 10. Компоненты по доменам

```
components/
├── admin/           DataCollectionTab, WorkerLogRelayPanel
├── ai/              ChatInput, ChatMessage, PresetQuestions, TypingIndicator
├── analytics/       TrendsChart, MarketComparisonSection
├── auth/            AuthProvider, AuthLayout, authContext
├── competitors/     ComparisonMatrix, PriceSparkline
├── dashboard/       MarketsTickerBar, Overview, Analytics sections
├── layout/          DashboardLayout, Sidebar, Header, Mobile, BottomNav
├── products/        MyProductsTab, PoolProductsTab, selection dialogs
├── ui/              shadcn primitives (button, card, table, dialog, …)
├── ui-custom/       PageHeader, StatCard, EmptyState, PlanLimitBanner, …
└── guards/          ProtectedRoute, SuperuserRoute, AIAnalystRoute, …
```

---

## 11. Entitlements и планы

- `useEntitlements` / `usePlanLimits` — лимиты products, AI route guard.
- `AIAnalystRoute` — редирект или upgrade prompt без entitlement.
- `PlanLimitBanner` — предупреждения в UI.

---

## 12. Безопасность (client)

- JWT в memory/storage через `authStorage` abstraction.
- DOMPurify для AI markdown render.
- HTTPS enforcement для API URL.
- ESLint security plugin (`lint:security`).
- Не хранить secrets во frontend env (только `VITE_*` public).

---

## 13. Тестирование

- **Unit:** Vitest (`npm test`).
- **E2E:** Playwright (отдельная конфигурация).
- **Admin parsing:** `AdminPage.parsing.test.tsx`.
- **i18n:** `src/i18n/__tests__/`.

---

## 14. Сборка и деплой

1. Push → Cloudflare Pages build `vite build`.
2. Env в Cloudflare: `VITE_API_URL` → Railway backend URL.
3. CORS на backend должен включать Pages origin.

---

## 15. Расхождения и TODO (зафиксировано)

| Тема | Состояние |
|------|-----------|
| `/competitors`, `/alerts` routes | Страницы и API clients есть, routes нет |
| Backend `/api/alerts` | Router не в main.py |
| `scraper/api.py` | Не подключён; admin parsing — основной путь |

---

## 16. Файлы-источники

| Область | Путь |
|---------|------|
| Routes | `frontend/src/App.tsx` |
| API client | `frontend/src/api/client.ts`, `admin.ts` |
| Admin UI | `frontend/src/components/admin/*` |
| Admin page | `frontend/src/pages/AdminPage.tsx` |
| Auth store | `frontend/src/stores/authStore.ts` |
| i18n | `frontend/src/i18n/index.ts` |

Связанные документы: `Imperecta_Architecture.md`, `Imperecta_Backend.md`, `Imperecta_Parsing.md`.
