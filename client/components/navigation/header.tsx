"use client"

import { Bell, Globe, Menu, Search, Sun, Moon } from "lucide-react"
import { Button } from "@/client/components/ui/button"
import { Input } from "@/client/components/ui/input"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/client/components/ui/dropdown-menu"
import { Avatar, AvatarFallback, AvatarImage } from "@/client/components/ui/avatar"
import { useLanguage } from "@/client/i18n/language-context"
import type { Language } from "@/client/i18n/translations"
import { useTheme } from "next-themes"
import { useSession, signOut } from "next-auth/react"
import Image from "next/image"

interface HeaderProps {
  onMenuButtonClick: () => void
}

export function Header({ onMenuButtonClick }: HeaderProps) {
  const { language, setLanguage, t } = useLanguage()
  const { theme, setTheme } = useTheme()
  const { data: session } = useSession()
  const user = session?.user

  const languages = [
    { code: "en", name: t("common", "english") },
    { code: "ru", name: t("common", "russian") },
    { code: "uk", name: t("common", "ukrainian") },
    { code: "ro", name: t("common", "romanian") },
  ]

  return (
    <header className="header-glass sticky top-0 z-30 flex h-16 items-center justify-between px-4 md:px-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" className="lg:hidden btn-glass" onClick={onMenuButtonClick}>
          <Menu className="h-5 w-5" />
        </Button>
        
        {/* Logo */}
        <div className="logo-container">
          <Image 
            src="/logo.png" 
            alt="Imperecta" 
            width={32} 
            height={32}
            className="dark:invert"
          />
          <span className="ml-2 font-semibold text-lg bg-gradient-to-r from-blue-600 via-purple-600 to-cyan-600 bg-clip-text text-transparent">
            Imperecta
          </span>
        </div>
      </div>

      <div className="hidden w-full max-w-sm md:flex mx-4">
        <div className="relative w-full">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            placeholder={t("common", "search")}
            className="input-glass w-full pl-10 focus-glass"
          />
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Button 
          variant="ghost" 
          size="icon" 
          className="btn-glass"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        >
          {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </Button>
        
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="btn-glass">
              <Globe className="h-5 w-5" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="glass">
            <DropdownMenuLabel>{t("common", "language")}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {languages.map((lang) => (
              <DropdownMenuItem
                key={lang.code}
                onClick={() => setLanguage(lang.code as Language)}
                className={language === lang.code ? "bg-muted" : ""}
              >
                {lang.name}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        
        <Button variant="ghost" size="icon" className="btn-glass relative">
          <Bell className="h-5 w-5" />
          <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-gradient-to-r from-red-500 to-pink-500 animate-pulse" />
        </Button>
        
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="btn-glass rounded-full">
              <Avatar className="h-8 w-8 ring-2 ring-primary/20">
                <AvatarImage src={user?.image || "/placeholder-user.jpg"} alt={user?.name || ""} />
                <AvatarFallback className="bg-gradient-to-br from-blue-500 to-purple-600 text-white">
                  {user?.name
                    ?.split(" ")
                    .map((n) => n[0])
                    .join("") || "U"}
                </AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="glass">
            <DropdownMenuLabel className="font-semibold">{user?.name}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <a href="/profile" className="flex items-center gap-2">
                <span>{t("common", "profile")}</span>
              </a>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <a href="/settings" className="flex items-center gap-2">
                <span>{t("common", "settings")}</span>
              </a>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem 
              onClick={() => signOut()}
              className="text-red-600 focus:text-red-600"
            >
              {t("common", "logout")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}
