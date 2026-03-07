/**
 * Sticky input area: textarea + Send button.
 * Enter → send, Shift+Enter → new line.
 */

import { useRef, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { SendHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const MAX_ROWS = 4;

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled?: boolean;
  className?: string;
}

export function ChatInput({ onSend, disabled, className }: ChatInputProps) {
  const { t } = useTranslation();
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  }, [value, disabled, onSend]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const lineHeight = 24;
    const rows = Math.min(MAX_ROWS, Math.max(1, Math.floor(el.scrollHeight / lineHeight)));
    el.style.height = `${rows * lineHeight}px`;
  };

  return (
    <div
      className={cn(
        "flex gap-2 rounded-xl border border-border bg-card p-3 dark:border-border",
        className
      )}
    >
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          handleInput();
        }}
        onKeyDown={handleKeyDown}
        onInput={handleInput}
        placeholder={t("ai.placeholder")}
        disabled={disabled}
        rows={1}
        className="min-h-[24px] max-h-[96px] flex-1 resize-none bg-transparent text-sm outline-none placeholder:text-muted-foreground disabled:opacity-50"
      />
      <Button
        size="icon"
        onClick={handleSubmit}
        disabled={!value.trim() || disabled}
        className="shrink-0"
        aria-label={t("ai.send")}
      >
        <SendHorizontal className="size-4" />
      </Button>
    </div>
  );
}
