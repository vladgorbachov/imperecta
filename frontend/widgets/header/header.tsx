import { Bell, Globe, Menu, Moon, Search, Sun, LogOut, User, Settings } from "lucide-react"
import { Button } from "@/shared/components/ui/button"
import { Input } from "@/shared/components/ui/input"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu"
import { Avatar, AvatarFallback, AvatarImage } from "@/shared/components/ui/avatar"
import { useTheme } from "@/app/providers/theme-provider"
import { useLanguage } from "@/app/providers/language-provider"
import { useSupabase } from "@/shared/contexts/supabase-context"
import { useNavigate } from "react-router-dom"

interface HeaderProps {
  onMenuButtonClick: () => void
}

export function Header({ onMenuButtonClick }: HeaderProps) {
  const { theme, setTheme } = useTheme()
  const { language, setLanguage } = useLanguage()
  const { user, signOut } = useSupabase()
  const navigate = useNavigate()

  const languages = [
    { code: "en", name: "English" },
    { code: "ru", name: "Русский" },
    { code: "es", name: "Español" },
    { code: "fr", name: "Français" },
    { code: "de", name: "Deutsch" },
    { code: "it", name: "Italiano" },
    { code: "pt", name: "Português" },
    { code: "ja", name: "日本語" },
    { code: "ko", name: "한국어" },
    { code: "zh", name: "中文" },
    { code: "ar", name: "العربية" },
    { code: "hi", name: "हिन्दी" },
    { code: "tr", name: "Türkçe" },
    { code: "pl", name: "Polski" },
    { code: "nl", name: "Nederlands" },
    { code: "sv", name: "Svenska" },
    { code: "da", name: "Dansk" },
    { code: "no", name: "Norsk" },
    { code: "fi", name: "Suomi" },
    { code: "cs", name: "Čeština" },
    { code: "sk", name: "Slovenčina" },
    { code: "hu", name: "Magyar" },
    { code: "ro", name: "Română" },
  ]

  const handleSignOut = async () => {
    try {
      const { error } = await signOut()
      if (error) {
        console.error('Sign out error:', error)
      } else {
        navigate("/login")
      }
    } catch (error) {
      console.error('Sign out error:', error)
    }
  }

  return (
    <header className="header-glass sticky top-0 z-30 flex h-16 items-center justify-end px-4 md:px-6">
      <div className="flex items-center gap-2">
        <div className="hidden md:flex">
          <div className="relative w-48">
            <Search className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="search"
              placeholder="Search..."
              className="input-glass w-full pl-10 focus-glass"
            />
          </div>
        </div>
        
        <Button 
          variant="ghost" 
          size="icon" 
          className="lg:hidden header-btn" 
          onClick={onMenuButtonClick}
        >
          <Menu className="h-5 w-5 header-icon" />
        </Button>
        
        <Button 
          variant="ghost" 
          size="icon" 
          className="header-btn"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        >
          {theme === "dark" ? <Sun className="h-5 w-5 header-icon" /> : <Moon className="h-5 w-5 header-icon" />}
        </Button>
        
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="header-btn">
              <Globe className="h-5 w-5 header-icon" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="glass">
            <DropdownMenuLabel>Language</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {languages.map((lang) => (
              <DropdownMenuItem
                key={lang.code}
                onClick={() => setLanguage(lang.code as 'en' | 'ru' | 'es' | 'fr' | 'de')}
                className={language === lang.code ? "bg-muted" : ""}
              >
                {lang.name}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        
        <Button variant="ghost" size="icon" className="header-btn">
          <Bell className="h-5 w-5 header-icon" />
        </Button>
        
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="header-btn rounded-full">
              <Avatar className="h-8 w-8 ring-2 ring-primary/20">
                <AvatarImage src={user?.user_metadata?.avatar_url || "/placeholder-user.jpg"} alt={user?.user_metadata?.full_name || ""} />
                <AvatarFallback className="bg-gradient-to-br from-blue-500 to-purple-600 text-white">
                  {user?.user_metadata?.full_name
                    ?.split(" ")
                    .map((n: string) => n[0])
                    .join("") || user?.email?.charAt(0).toUpperCase() || "U"}
                </AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="glass">
            <DropdownMenuLabel className="font-semibold">{user?.user_metadata?.full_name || user?.email}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => navigate("/profile")}>
              <User className="mr-2 h-4 w-4" />
              Profile
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => navigate("/settings")}>
              <Settings className="mr-2 h-4 w-4" />
              Settings
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem 
              onClick={handleSignOut}
              className="text-red-600 focus:text-red-600"
            >
              <LogOut className="mr-2 h-4 w-4" />
              Logout
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}
