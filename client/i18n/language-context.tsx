"use client"

import { createContext, useContext, useState, useEffect, type ReactNode } from "react"
import { type Language, translations, type TranslationKey, type NestedTranslationKey } from "./translations"

type LanguageContextType = {
  language: Language
  setLanguage: (language: Language) => void
  t: <T extends TranslationKey, K extends NestedTranslationKey<T>>(section: T, key: K) => string
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>("en")

  useEffect(() => {
    const savedLanguage = localStorage.getItem("language") as Language
    if (savedLanguage && ["en", "ru", "uk", "ro"].includes(savedLanguage)) {
      setLanguage(savedLanguage)
    }
  }, [])

  useEffect(() => {
    localStorage.setItem("language", language)
  }, [language])

  const t = <T extends TranslationKey, K extends NestedTranslationKey<T>>(section: T, key: K): string => {
    return translations[language][section][key as keyof (typeof translations)[typeof language][T]] as string
  }

  return <LanguageContext.Provider value={{ language, setLanguage, t }}>{children}</LanguageContext.Provider>
}

export function useLanguage() {
  const context = useContext(LanguageContext)
  if (context === undefined) {
    throw new Error("useLanguage must be used within a LanguageProvider")
  }
  return context
}
