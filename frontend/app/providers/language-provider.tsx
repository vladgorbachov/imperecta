import { createContext, useContext, useState, ReactNode, useEffect } from 'react'
import { useSupabase } from '@/shared/contexts/supabase-context'

type Language = 'en' | 'ro' | 'ru' | 'uk' | 'pl' | 'hu' | 'hr' | 'sq' | 'be' | 'lv' | 'lt' | 'et' | 'es' | 'fr' | 'de' | 'pt' | 'zh-Hant' | 'hi'

interface LanguageContextType {
  language: Language
  setLanguage: (lang: Language) => void
  t: (section: string, key: string) => string
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined)

interface LanguageProviderProps {
  children: ReactNode
}

const base = {
  dashboard: 'Dashboard', overview: 'Overview', customers: 'Customers', sales: 'Sales', operations: 'Operations', inventory: 'Inventory', communications: 'Communications', marketing: 'Marketing',
  projects: 'Projects', tasks: 'Tasks', team: 'Team', clients: 'Clients', finance: 'Finance', documents: 'Documents', calendar: 'Calendar', analytics: 'Analytics', profile: 'Profile', settings: 'Settings', logout: 'Logout', login: 'Login', email: 'Email', password: 'Password', signIn: 'Sign In', addEmployee: 'Add Employee', search: 'Search', filter: 'Filter', sort: 'Sort', view: 'View', edit: 'Edit', delete: 'Delete', save: 'Save', cancel: 'Cancel', close: 'Close', open: 'Open', loading: 'Loading...', error: 'Error', success: 'Success', warning: 'Warning', info: 'Information',
  schedule: 'Schedule', aiAssistant: 'AI Assistant', aiInsights: 'AI Insights', aiWorkers: 'AI Workers', contentPlan: 'Content Plan', campaigns: 'Campaigns', openAnalytics: 'Open Analytics', openInsights: 'Open AI Insights', weeklyReport: 'Weekly report', launchCampaign: 'Launch campaign', editorialMeeting: 'Editorial meeting',
  invoices: 'Invoices', budgets: 'Budgets', transactions: 'Transactions', remind: 'Remind', review: 'Review', createProject: 'Create Project', noProjects: 'No projects to display',
  // Dashboard KPI
  revenue: 'Revenue', newCustomers: 'New customers', tasksCompleted: 'Tasks completed', satisfaction: 'Satisfaction',
  // Common table/labels
  number: 'No.', client: 'Client', status: 'Status', issuedOn: 'Issued on', dueDate: 'Due date', amount: 'Amount', balance: 'Balance', name: 'Name', period: 'Period', dates: 'Dates', total: 'Total', allocated: 'Allocated', spent: 'Spent', remaining: 'Remaining', date: 'Date', type: 'Type', currency: 'Currency', from: 'From', to: 'To', reference: 'Reference',
  // Customers
  customersList: 'List', crmPipeline: 'CRM pipeline', segmentation: 'Segmentation', history: 'History', loyalty: 'Loyalty', allCustomers: 'All customers', newCustomer: 'New customer', inProgress: 'In progress', negotiations: 'Negotiations', won: 'Won', leadDeal: 'Lead/Deal',
  // Sales
  pipeline: 'Pipeline', quotes: 'Invoices & Quotes', proposals: 'Commercial proposals', salesAnalytics: 'Sales analytics', forecast: 'Forecast', newDeal: 'New deal',
  // Operations
  processes: 'Processes', automation: 'Automation', workflows: 'Workflows', sop: 'SOP', quality: 'Quality', businessProcesses: 'Business processes', drafts: 'Drafts', active: 'Active', onReview: 'On review',
  // Inventory
  items: 'Products & Services', stock: 'Stock Levels', suppliers: 'Suppliers', purchaseOrders: 'Purchase Orders', tracking: 'Tracking', productsAndServices: 'Products and Services', stocks: 'Stocks', suppliersList: 'Suppliers', orders: 'Orders', trackingHistory: 'Tracking history',
  // Communications
  communicationsTitle: 'Communications', emailCampaigns: 'Email Campaigns', chatsMessengers: 'Chats/Messengers', meetingsCalendar: 'Meetings Calendar', notifications: 'Notifications', knowledgeBase: 'Knowledge Base', lists: 'Lists', chats: 'Chats', meetings: 'Meetings', integrationWithCalendar: 'Integration with Calendar', rules: 'Rules', documentsLabel: 'Documents',
  // Calendar
  today: 'Today', searchEvents: 'Search events...', events: 'events', add: 'Add', addEvent: 'Add Event', noEvents: 'No events scheduled', more: 'more',
  sun: 'Sun', mon: 'Mon', tue: 'Tue', wed: 'Wed', thu: 'Thu', fri: 'Fri', sat: 'Sat',
  // Dashboard
  quickActions: 'Quick actions', revenueWeek: 'Revenue (week)', activities: 'Activities',
  newInvoice: 'New invoice', addCustomerAction: 'Add customer', createTaskAction: 'Create task', reportAction: 'Report',
} as Record<string, string>

const translations: Record<Language, Record<string, string>> = {
  en: { ...base },
  ru: { ...base, dashboard: 'Панель управления', overview: 'Обзор', customers: 'Клиенты', sales: 'Продажи', operations: 'Операции', inventory: 'Склад', communications: 'Коммуникации', marketing: 'Маркетинг', projects: 'Проекты', tasks: 'Задачи', team: 'Команда', clients: 'Клиенты', finance: 'Финансы', documents: 'Документы', calendar: 'Календарь', analytics: 'Аналитика', profile: 'Профиль', settings: 'Настройки', logout: 'Выйти', login: 'Войти', signIn: 'Войти', addEmployee: 'Добавить сотрудника', search: 'Поиск', filter: 'Фильтр', sort: 'Сортировка', view: 'Просмотр', edit: 'Редактировать', delete: 'Удалить', save: 'Сохранить', cancel: 'Отмена', close: 'Закрыть', open: 'Открыть', loading: 'Загрузка...', error: 'Ошибка', success: 'Успех', warning: 'Предупреждение', info: 'Информация', schedule: 'Запланировать', aiAssistant: 'ИИ Ассистент', aiInsights: 'AI Инсайты', aiWorkers: 'AI Работники', contentPlan: 'Контент-план', campaigns: 'Кампании', openAnalytics: 'Открыть Аналитику', openInsights: 'Открыть AI Инсайты', weeklyReport: 'Еженедельный отчёт', launchCampaign: 'Запуск кампании', editorialMeeting: 'Встреча по редакторскому календарю', invoices: 'Счета', budgets: 'Бюджеты', transactions: 'Транзакции', remind: 'Напомнить', review: 'Ревью', createProject: 'Создать проект', noProjects: 'Нет проектов для отображения', number: '№', client: 'Клиент', status: 'Статус', issuedOn: 'Выставлен', dueDate: 'Срок оплаты', amount: 'Сумма', balance: 'Баланс', name: 'Название', period: 'Период', dates: 'Даты', total: 'Итого', allocated: 'Выделено', spent: 'Потрачено', remaining: 'Остаток', date: 'Дата', type: 'Тип', currency: 'Валюта', from: 'Счет от', to: 'Счет к', reference: 'Референс', customersList: 'Список', crmPipeline: 'CRM pipeline', segmentation: 'Сегментация', history: 'История', loyalty: 'Лояльность', allCustomers: 'Все клиенты', newCustomer: 'Новый клиент', inProgress: 'В работе', negotiations: 'Переговоры', won: 'Успешно', leadDeal: 'Лид/Сделка', pipeline: 'Воронка', quotes: 'Счета и квоты', proposals: 'Коммерческие предложения', salesAnalytics: 'Аналитика продаж', forecast: 'Прогноз', newDeal: 'Новая сделка', processes: 'Процессы', automation: 'Автоматизация', workflows: 'Рабочие потоки', sop: 'SOP', quality: 'Качество', businessProcesses: 'Бизнес-процессы', drafts: 'Черновики', active: 'Активные', onReview: 'На ревью', items: 'Товары и услуги', stock: 'Остатки', suppliers: 'Поставщики', purchaseOrders: 'Заказы на поставку', tracking: 'Отслеживание', productsAndServices: 'Товары и услуги', stocks: 'Остатки', suppliersList: 'Поставщики', orders: 'Заказы', trackingHistory: 'История движений', communicationsTitle: 'Коммуникации', emailCampaigns: 'Email кампании', chatsMessengers: 'Чаты/мессенджеры', meetingsCalendar: 'Календарь встреч', notifications: 'Уведомления', knowledgeBase: 'База знаний', lists: 'Список', chats: 'Чаты', meetings: 'Встречи', integrationWithCalendar: 'Интеграция с Календарём', rules: 'Правила', documentsLabel: 'Документы', today: 'Сегодня', searchEvents: 'Поиск событий...', events: 'событий', add: 'Добавить', addEvent: 'Добавить событие', noEvents: 'Событий не запланировано', more: 'ещё', sun: 'Вс', mon: 'Пн', tue: 'Вт', wed: 'Ср', thu: 'Чт', fri: 'Пт', sat: 'Сб', revenue: 'Выручка', newCustomers: 'Новые клиенты', tasksCompleted: 'Выполнено задач', satisfaction: 'Удовлетворенность', quickActions: 'Быстрые действия', revenueWeek: 'Выручка (неделя)', activities: 'Активности', newInvoice: 'Новый счет', addCustomerAction: 'Добавить клиента', createTaskAction: 'Создать задачу', reportAction: 'Отчет' },
  es: { ...base, dashboard: 'Panel de control', overview: 'Resumen', customers: 'Clientes', sales: 'Ventas', operations: 'Operaciones', inventory: 'Inventario', communications: 'Comunicaciones', marketing: 'Marketing', finance: 'Finanzas', documents: 'Documentos', calendar: 'Calendario', analytics: 'Analíticas' },
  fr: { ...base, dashboard: 'Tableau de bord', overview: 'Aperçu', customers: 'Clients', sales: 'Ventes', operations: 'Opérations', inventory: 'Inventaire', communications: 'Communications', marketing: 'Marketing' },
  de: { ...base, dashboard: 'Dashboard', overview: 'Überblick', customers: 'Kunden', sales: 'Vertrieb', operations: 'Betrieb', inventory: 'Inventar', communications: 'Kommunikation', marketing: 'Marketing' },
  pt: { ...base, dashboard: 'Painel', overview: 'Visão geral', customers: 'Clientes', sales: 'Vendas', operations: 'Operações', inventory: 'Inventário', communications: 'Comunicações', marketing: 'Marketing' },
  'zh-Hant': { ...base, dashboard: '儀表板', overview: '總覽', customers: '客戶', sales: '銷售', operations: '營運', inventory: '庫存', communications: '通信', marketing: '行銷', calendar: '行事曆' },
  hi: { ...base, dashboard: 'डैशबोर्ड', overview: 'अवलोकन', customers: 'ग्राहक', sales: 'बिक्री', operations: 'ऑपरेशंस', inventory: 'इन्वेंटरी', communications: 'संचार', marketing: 'मार्केटिंग', calendar: 'कैलेंडर' },
  ro: { ...base, dashboard: 'Panou', overview: 'Prezentare', customers: 'Clienți', sales: 'Vânzări', operations: 'Operațiuni', inventory: 'Inventar', communications: 'Comunicări', marketing: 'Marketing' },
  uk: { ...base, dashboard: 'Огляд', overview: 'Огляд', customers: 'Клієнти', sales: 'Продажі', operations: 'Операції', inventory: 'Склад', communications: 'Комунікації', marketing: 'Маркетинг', projects: 'Проєкти', tasks: 'Завдання', team: 'Команда', clients: 'Клієнти', finance: 'Фінанси', documents: 'Документи', calendar: 'Календар', analytics: 'Аналітика', schedule: 'Запланувати', aiAssistant: 'AI Асистент', aiInsights: 'AI Інсайти', aiWorkers: 'AI Працівники', contentPlan: 'Контент-план', campaigns: 'Кампанії', openAnalytics: 'Відкрити Аналітику', openInsights: 'Відкрити AI Інсайти', weeklyReport: 'Щотижневий звіт', launchCampaign: 'Запуск кампанії', editorialMeeting: 'Зустріч щодо редакційного календаря', invoices: 'Рахунки', budgets: 'Бюджети', transactions: 'Транзакції', remind: 'Нагадати', review: 'Огляд', createProject: 'Створити проєкт', noProjects: 'Немає проєктів для відображення', number: '№', client: 'Клієнт', status: 'Статус', issuedOn: 'Виставлено', dueDate: 'Термін оплати', amount: 'Сума', balance: 'Баланс', name: 'Назва', period: 'Період', dates: 'Дати', total: 'Разом', allocated: 'Виділено', spent: 'Витрачено', remaining: 'Залишок', date: 'Дата', type: 'Тип', currency: 'Валюта', from: 'Рахунок від', to: 'Рахунок до', reference: 'Референс', customersList: 'Список', crmPipeline: 'CRM pipeline', segmentation: 'Сегментація', history: 'Історія', loyalty: 'Лояльність', allCustomers: 'Усі клієнти', newCustomer: 'Новий клієнт', inProgress: 'В роботі', negotiations: 'Перемовини', won: 'Успішно', leadDeal: 'Лід/Угода', pipeline: 'Воронка', quotes: 'Рахунки і квоти', proposals: 'Комерційні пропозиції', salesAnalytics: 'Аналітика продажів', forecast: 'Прогноз', newDeal: 'Нова угода', processes: 'Процеси', automation: 'Автоматизація', workflows: 'Потоки', sop: 'SOP', quality: 'Якість', businessProcesses: 'Бізнес-процеси', drafts: 'Чернетки', active: 'Активні', onReview: 'На перегляді', items: 'Товари та послуги', stock: 'Залишки', suppliers: 'Постачальники', purchaseOrders: 'Замовлення на постачання', tracking: 'Відстеження', productsAndServices: 'Товари та послуги', stocks: 'Залишки', suppliersList: 'Постачальники', orders: 'Замовлення', trackingHistory: 'Історія переміщень', communicationsTitle: 'Комунікації', emailCampaigns: 'Email кампанії', chatsMessengers: 'Чати/месенджери', meetingsCalendar: 'Календар зустрічей', notifications: 'Сповіщення', knowledgeBase: 'База знань', lists: 'Списки', chats: 'Чати', meetings: 'Зустрічі', integrationWithCalendar: 'Інтеграція з Календарем', rules: 'Правила', documentsLabel: 'Документи', today: 'Сьогодні', searchEvents: 'Пошук подій...', events: 'подій', add: 'Додати', addEvent: 'Додати подію', noEvents: 'Подій не заплановано', more: 'ще', sun: 'Нд', mon: 'Пн', tue: 'Вт', wed: 'Ср', thu: 'Чт', fri: 'Пт', sat: 'Сб', revenue: 'Виручка', newCustomers: 'Нові клієнти', tasksCompleted: 'Виконано завдань', satisfaction: 'Задоволеність', quickActions: 'Швидкі дії', revenueWeek: 'Виручка (тиждень)', activities: 'Активності', newInvoice: 'Новий рахунок', addCustomerAction: 'Додати клієнта', createTaskAction: 'Створити завдання', reportAction: 'Звіт' },
  pl: { ...base, dashboard: 'Pulpit', overview: 'Przegląd', customers: 'Klienci', sales: 'Sprzedaż', operations: 'Operacje', inventory: 'Magazyn', communications: 'Komunikacja', marketing: 'Marketing' },
  hu: { ...base, dashboard: 'Vezérlőpult', overview: 'Áttekintés', customers: 'Ügyfelek', sales: 'Értékesítés', operations: 'Műveletek', inventory: 'Készlet', communications: 'Kommunikáció', marketing: 'Marketing' },
  hr: { ...base, dashboard: 'Pregled', overview: 'Pregled', customers: 'Klijenti', sales: 'Prodaja', operations: 'Operacije', inventory: 'Skladište', communications: 'Komunikacije', marketing: 'Marketing' },
  sq: { ...base, dashboard: 'Paneli', overview: 'Përmbledhje', customers: 'Klientët', sales: 'Shitje', operations: 'Operacionet', inventory: 'Inventari', communications: 'Komunikimet', marketing: 'Marketing' },
  be: { ...base, dashboard: 'Панэль', overview: 'Агляд', customers: 'Кліенты', sales: 'Продажы', operations: 'Аперацыі', inventory: 'Склад', communications: 'Камунікацыі', marketing: 'Маркетынг' },
  lv: { ...base, dashboard: 'Panelis', overview: 'Pārskats', customers: 'Klienti', sales: 'Pārdošana', operations: 'Operācijas', inventory: 'Krājumi', communications: 'Komunikācija', marketing: 'Mārketings' },
  lt: { ...base, dashboard: 'Skydelis', overview: 'Apžvalga', customers: 'Klientai', sales: 'Pardavimai', operations: 'Operacijos', inventory: 'Atsargos', communications: 'Komunikacijos', marketing: 'Marketingas' },
  et: { ...base, dashboard: 'Töölaud', overview: 'Ülevaade', customers: 'Kliendid', sales: 'Müük', operations: 'Tegevused', inventory: 'Ladu', communications: 'Suhtlus', marketing: 'Turundus' },
}

export function LanguageProvider({ children }: LanguageProviderProps) {
  const { user } = useSupabase()
  const [language, setLanguage] = useState<Language>('en')

  useEffect(() => {
    const saved = (localStorage.getItem('lang') as Language) || null
    if (saved && (translations as any)[saved]) {
      setLanguage(saved)
      return
    }
    const metaLang = (user?.user_metadata?.language || user?.user_metadata?.lang || '').trim()
    if (metaLang && (translations as any)[metaLang]) {
      setLanguage(metaLang as Language)
    }
  }, [user])

  const setLanguagePersist = (lang: Language) => {
    setLanguage(lang)
    localStorage.setItem('lang', lang)
  }

  const t = (_section: string, key: string): string => {
    const sectionTranslations = translations[language] as Record<string, string>
    return sectionTranslations[key] || translations['en'][key] || key
  }

  return (
    <LanguageContext.Provider value={{ language, setLanguage: setLanguagePersist, t }}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useLanguage() {
  const context = useContext(LanguageContext)
  if (context === undefined) {
    throw new Error('useLanguage must be used within a LanguageProvider')
  }
  return context
}
