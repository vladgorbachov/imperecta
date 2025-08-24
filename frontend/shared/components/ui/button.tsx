import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/shared/utils/cn"

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 btn-uniform",
  {
    variants: {
      variant: {
        default: "btn-glossy bg-white text-sky-600 hover:brightness-95 active:brightness-90 dark:bg-white/10 dark:text-white dark:border dark:border-white/20 dark:backdrop-blur-md dark:hover:bg-white/20 dark:shadow-[0_8px_32px_rgba(0,0,0,0.3)]",
        destructive:
          "btn-glossy text-red-600 hover:brightness-95 active:brightness-90 bg-white border border-red-200 dark:bg-red-500/20 dark:text-red-200 dark:border dark:border-red-400/30 dark:hover:bg-red-500/30",
        outline:
          "btn-glossy text-sky-600 bg-white border border-input hover:brightness-95 active:brightness-90 dark:bg-white/5 dark:border-white/20 dark:hover:bg-white/15 dark:text-white",
        secondary:
          "btn-glossy text-sky-600 bg-white hover:brightness-95 active:brightness-90 dark:bg-white/10 dark:text-white dark:border dark:border-white/20 dark:hover:bg-white/20",
        ghost: "hover:bg-accent hover:text-accent-foreground dark:hover:bg-white/10 dark:text-white",
        link: "text-sky-600 underline-offset-4 hover:underline dark:text-blue-400",
      },
      size: {
        default: "",
        sm: "",
        lg: "",
        icon: "",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        data-size={size === 'icon' ? 'icon' : undefined}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
