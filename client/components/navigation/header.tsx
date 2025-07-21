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
// import type { User } from "@/types/user" // This is no longer needed

interface HeaderProps {
  onMenuButtonClick: () => void
}

export function Header({ onMenuButtonClick }: HeaderProps) {
  const { language, setLanguage, t } = useLanguage()
  const { theme, setTheme } = useTheme()
  const { data: session } = useSession()
  const user = session?.user // The user object is now correctly typed from useSession

  const languages = [
    { code: "en", name: t("common", "english") },
    { code: "ru", name: t("common", "russian") },
    { code: "uk", name: t("common", "ukrainian") },
    { code: "ro", name: t("common", "romanian") },
  ]

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b bg-card px-4 md:px-6">
      <Button variant="ghost" size="icon" className="lg:hidden" onClick={onMenuButtonClick}>
        <Menu className="h-5 w-5" />
      </Button>
      <div className="hidden w-full max-w-sm md:flex">
        <div className="relative w-full">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            type="search"
            placeholder={t("common", "search")}
            className="w-full rounded-md border bg-background pl-8"
          />
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
          {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon">
              <Globe className="h-5 w-5" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
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
        <Button variant="ghost" size="icon" className="relative">
          <Bell className="h-5 w-5" />
          <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-primary" />
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="rounded-full">
              <Avatar className="h-8 w-8">
                <AvatarImage src={user?.avatar || "/placeholder.svg"} alt={user?.name || ""} />
                <AvatarFallback>
                  {user?.name
                    .split(" ")
                    .map((n) => n[0])
                    .join("")}
                </AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>{user?.name}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <a href="/profile">{t("common", "profile")}</a>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <a href="/settings">{t("common", "settings")}</a>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => signOut()}>{t("common", "logout")}</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}
