/**
 * Animated 3-dot typing indicator when AI is "thinking".
 */

import { cn } from "@/lib/utils";

export function TypingIndicator({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-1", className)}>
      <span className="size-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:0ms]" />
      <span className="size-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:150ms]" />
      <span className="size-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:300ms]" />
    </div>
  );
}
