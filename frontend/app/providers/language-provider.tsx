import { createContext, useContext, useState, ReactNode } from 'react'

type Language = 'en' | 'ru' | 'es' | 'fr' | 'de'

interface LanguageContextType {
  language: Language
  setLanguage: (lang: Language) => void
  t: (section: string, key: string) => string
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined)

interface LanguageProviderProps {
  children: ReactNode
}

const translations = {
  en: {
    dashboard: 'Dashboard',
    projects: 'Projects',
    tasks: 'Tasks',
    team: 'Team',
    clients: 'Clients',
    finance: 'Finance',
    documents: 'Documents',
    calendar: 'Calendar',
    analytics: 'Analytics',
    profile: 'Profile',
    settings: 'Settings',
    logout: 'Logout',
    login: 'Login',
    email: 'Email',
    password: 'Password',
    signIn: 'Sign In',
    addEmployee: 'Add Employee',
    search: 'Search',
    filter: 'Filter',
    sort: 'Sort',
    view: 'View',
    edit: 'Edit',
    delete: 'Delete',
    save: 'Save',
    cancel: 'Cancel',
    close: 'Close',
    open: 'Open',
    loading: 'Loading...',
    error: 'Error',
    success: 'Success',
    warning: 'Warning',
    info: 'Information',
  },
  ru: {
    dashboard: 'Панель управления',
    projects: 'Проекты',
    tasks: 'Задачи',
    team: 'Команда',
    clients: 'Клиенты',
    finance: 'Финансы',
    documents: 'Документы',
    calendar: 'Календарь',
    analytics: 'Аналитика',
    profile: 'Профиль',
    settings: 'Настройки',
    logout: 'Выйти',
    login: 'Войти',
    email: 'Email',
    password: 'Пароль',
    signIn: 'Войти',
    addEmployee: 'Добавить сотрудника',
    search: 'Поиск',
    filter: 'Фильтр',
    sort: 'Сортировка',
    view: 'Просмотр',
    edit: 'Редактировать',
    delete: 'Удалить',
    save: 'Сохранить',
    cancel: 'Отмена',
    close: 'Закрыть',
    open: 'Открыть',
    loading: 'Загрузка...',
    error: 'Ошибка',
    success: 'Успех',
    warning: 'Предупреждение',
    info: 'Информация',
  },
  es: {
    dashboard: 'Panel de control',
    projects: 'Proyectos',
    tasks: 'Tareas',
    team: 'Equipo',
    clients: 'Clientes',
    finance: 'Finanzas',
    documents: 'Documentos',
    calendar: 'Calendario',
    analytics: 'Analíticas',
    profile: 'Perfil',
    settings: 'Configuración',
    logout: 'Cerrar sesión',
    login: 'Iniciar sesión',
    email: 'Email',
    password: 'Contraseña',
    signIn: 'Iniciar sesión',
    addEmployee: 'Agregar empleado',
    search: 'Buscar',
    filter: 'Filtrar',
    sort: 'Ordenar',
    view: 'Ver',
    edit: 'Editar',
    delete: 'Eliminar',
    save: 'Guardar',
    cancel: 'Cancelar',
    close: 'Cerrar',
    open: 'Abrir',
    loading: 'Cargando...',
    error: 'Error',
    success: 'Éxito',
    warning: 'Advertencia',
    info: 'Información',
  },
  fr: {
    dashboard: 'Tableau de bord',
    projects: 'Projets',
    tasks: 'Tâches',
    team: 'Équipe',
    clients: 'Clients',
    finance: 'Finance',
    documents: 'Documents',
    calendar: 'Calendrier',
    analytics: 'Analyses',
    profile: 'Profil',
    settings: 'Paramètres',
    logout: 'Déconnexion',
    login: 'Connexion',
    email: 'Email',
    password: 'Mot de passe',
    signIn: 'Se connecter',
    addEmployee: 'Ajouter un employé',
    search: 'Rechercher',
    filter: 'Filtrer',
    sort: 'Trier',
    view: 'Voir',
    edit: 'Modifier',
    delete: 'Supprimer',
    save: 'Enregistrer',
    cancel: 'Annuler',
    close: 'Fermer',
    open: 'Ouvrir',
    loading: 'Chargement...',
    error: 'Erreur',
    success: 'Succès',
    warning: 'Avertissement',
    info: 'Information',
  },
  de: {
    dashboard: 'Dashboard',
    projects: 'Projekte',
    tasks: 'Aufgaben',
    team: 'Team',
    clients: 'Kunden',
    finance: 'Finanzen',
    documents: 'Dokumente',
    calendar: 'Kalender',
    analytics: 'Analysen',
    profile: 'Profil',
    settings: 'Einstellungen',
    logout: 'Abmelden',
    login: 'Anmelden',
    email: 'E-Mail',
    password: 'Passwort',
    signIn: 'Anmelden',
    addEmployee: 'Mitarbeiter hinzufügen',
    search: 'Suchen',
    filter: 'Filter',
    sort: 'Sortieren',
    view: 'Anzeigen',
    edit: 'Bearbeiten',
    delete: 'Löschen',
    save: 'Speichern',
    cancel: 'Abbrechen',
    close: 'Schließen',
    open: 'Öffnen',
    loading: 'Laden...',
    error: 'Fehler',
    success: 'Erfolg',
    warning: 'Warnung',
    info: 'Information',
  },
}

export function LanguageProvider({ children }: LanguageProviderProps) {
  const [language, setLanguage] = useState<Language>('en')

  const t = (_section: string, key: string): string => {
    const sectionTranslations = translations[language] as Record<string, string>
    return sectionTranslations[key] || key
  }

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
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
