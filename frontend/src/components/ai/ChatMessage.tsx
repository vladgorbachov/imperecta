/**
 * Single chat message: user (right) or AI (left, with avatar, markdown).
 */

import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";
import { Bot, Copy, MoreHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

interface ChatMessageProps {
  message: ChatMessage;
  onCopy?: () => void;
}

export function ChatMessageComponent({ message, onCopy }: ChatMessageProps) {
  const { t } = useTranslation();
  const isUser = message.role === "user";

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    onCopy?.();
  };

  return (
    <div
      className={cn(
        "flex gap-3 animate-in fade-in-0 slide-in-from-bottom-2 duration-300",
        isUser && "flex-row-reverse"
      )}
    >
      {!isUser && (
        <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-primary/10">
          <Bot className="size-6 text-primary" />
        </div>
      )}
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-3 shadow-sm",
          isUser
            ? "bg-accent/20 dark:bg-accent/20"
            : "bg-card/80 backdrop-blur-sm dark:bg-card/80"
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap text-sm">{message.content}</p>
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown
              components={{
                h1: ({ children }) => (
                  <h1 className="mb-2 mt-4 text-lg font-bold first:mt-0">{children}</h1>
                ),
                h2: ({ children }) => (
                  <h2 className="mb-2 mt-3 text-base font-semibold">{children}</h2>
                ),
                ul: ({ children }) => (
                  <ul className="my-2 list-inside list-disc space-y-1">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="my-2 list-inside list-decimal space-y-1">{children}</ol>
                ),
                code: ({ children }) => (
                  <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{children}</code>
                ),
                table: ({ children }) => (
                  <div className="my-2 overflow-x-auto">
                    <table className="min-w-full border-collapse border border-border">{children}</table>
                  </div>
                ),
                th: ({ children }) => (
                  <th className="border border-border bg-muted/50 px-2 py-1 text-left text-sm font-medium">
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td className="border border-border px-2 py-1 text-sm">{children}</td>
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}
        {!isUser && (
          <div className="mt-2 flex gap-1">
            <Button variant="ghost" size="sm" className="h-2 px-2 text-xs" onClick={handleCopy}>
              <Copy className="mr-1 size-3" />
              {t("ai.copy")}
            </Button>
            <Button variant="ghost" size="sm" className="h-2 px-2 text-xs">
              <MoreHorizontal className="mr-1 size-3" />
              {t("ai.more")}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
