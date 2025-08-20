import * as React from "react"
import { ThemeProvider as NextThemesProvider } from "next-themes"
import type { ThemeProviderProps } from "next-themes"

interface CustomThemeProviderProps extends ThemeProviderProps {
  children: React.ReactNode
}

export function ThemeProvider({ children, ...props }: CustomThemeProviderProps) {
  return <NextThemesProvider {...props}>{children}</NextThemesProvider>
}

export function useTheme() {
  const [theme, setTheme] = React.useState<'light' | 'dark' | 'system'>('system')
  const [mounted, setMounted] = React.useState(false)

  const updateTheme = (newTheme: 'light' | 'dark' | 'system') => {
    setTheme(newTheme)
    localStorage.setItem('theme', newTheme)

    if (newTheme === 'dark') {
      document.documentElement.classList.add('dark')
    } else if (newTheme === 'light') {
      document.documentElement.classList.remove('dark')
    } else {
      const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
      if (systemTheme === 'dark') {
        document.documentElement.classList.add('dark')
      } else {
        document.documentElement.classList.remove('dark')
      }
    }
  }

  React.useEffect(() => {
    const savedTheme = (localStorage.getItem('theme') as 'light' | 'dark' | 'system') || 'system'
    if (savedTheme === 'system') {
      const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
      updateTheme(systemTheme)
    } else {
      updateTheme(savedTheme)
    }
    setMounted(true)
  }, [])

  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light'
    updateTheme(newTheme)
  }

  if (!mounted) {
    return { theme: 'light' as const, setTheme: updateTheme, toggleTheme }
  }

  return { theme, setTheme: updateTheme, toggleTheme }
}
