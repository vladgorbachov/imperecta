"use client"

import Image from "next/image"
import { useTheme } from "next-themes"
import { useEffect, useState } from "react"

export function Logo() {
  const { theme } = useTheme()
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  // Prevent hydration mismatch by not rendering until mounted
  if (!mounted) {
    return (
      <div className="relative w-[200px] h-[70px]">
        <Image
          src="https://hebbkx1anhila5yf.public.blob.vercel-storage.com/Light.png-khJtYN6jEnssaszQexfeRukZH9rNYW.jpeg"
          alt="Imperecta Logo"
          fill
          className="object-contain"
          priority
          sizes="200px"
        />
      </div>
    )
  }

  return (
    <div className="relative w-[200px] h-[70px]">
      <Image
        src={
          theme === "dark"
            ? "https://hebbkx1anhila5yf.public.blob.vercel-storage.com/Imperecta%20%28%D0%9B%D0%BE%D0%B3%D0%BE%D1%82%D0%B8%D0%BF%29%20%282%29.png-H49dO4G4lx6JGD2h3YktpDgtUt1slK.jpeg"
            : "https://hebbkx1anhila5yf.public.blob.vercel-storage.com/Light.png-khJtYN6jEnssaszQexfeRukZH9rNYW.jpeg"
        }
        alt="Imperecta Logo"
        fill
        className="object-contain"
        priority
        sizes="200px"
      />
    </div>
  )
}
