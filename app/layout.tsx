import type React from "react"
import type { Metadata } from "next"
import { ThemeProvider } from "@/client/components/theme-provider"
import { LanguageProvider } from "@/client/i18n/language-context"
import { SessionProvider } from "@/client/components/session-provider"
import "./globals.css"

export const metadata: Metadata = {
  title: "Imperecta - Enterprise Management System",
  description: "Administration platform for small and medium businesses",
  icons: {
    icon: [
      {
        url: "/favicon.ico",
        sizes: "any",
      },
      {
        url: "/icon.svg",
        type: "image/svg+xml",
      },
    ],
    apple: "/apple-touch-icon.png",
  },
    generator: 'v0.dev'
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning className="dark">
      <head />
      <body>
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false} disableTransitionOnChange>
          <SessionProvider>
            <LanguageProvider>{children}</LanguageProvider>
          </SessionProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}
