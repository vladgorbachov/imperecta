import { useEffect, useState } from "react"

export function Logo() {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  // Prevent hydration mismatch by not rendering until mounted
  if (!mounted) {
    return (
      <div className="flex items-center justify-center w-full">
        <div className="text-center">
          <div className="flex items-center justify-center mb-3">
            <img 
              src="/logo.png" 
              alt="Imperecta" 
              width="80" 
              height="64"
              className="dark:invert"
            />
          </div>
          <div className="text-black dark:text-white font-bold text-xl tracking-wider text-center">IMPERECTA</div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-center justify-center w-full">
      <div className="text-center">
        <div className="flex items-center justify-center mb-3">
          <img 
            src="/logo.png" 
            alt="Imperecta" 
            width="80" 
            height="64"
            className="dark:invert"
          />
        </div>
        <div className="text-black dark:text-white font-bold text-xl tracking-wider text-center">IMPERECTA</div>
      </div>
    </div>
  )
}
