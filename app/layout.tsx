import type React from "react"
import type { Metadata } from "next"
import { ThemeProvider } from "@/client/components/theme-provider"
import { LanguageProvider } from "@/client/i18n/language-context"
import { SessionProvider } from "@/client/components/session-provider"
import "./globals.css"

export const metadata: Metadata = {
  title: "Imperecta - Enterprise Management System",
  description: "Modern administration platform with glass morphism design for small and medium businesses",
  icons: {
    icon: [
      {
        url: "/favicon.ico",
        sizes: "any",
      },
      {
        url: "/icon.png",
        sizes: "32x32",
        type: "image/png",
      },
    ],
    apple: "/icon.png",
  },
  generator: 'Imperecta v1.0'
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head />
      <body>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem={true} disableTransitionOnChange>
          <SessionProvider>
            <LanguageProvider>{children}</LanguageProvider>
          </SessionProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}
