// MOBILE-2026: fully responsive + bottom nav + drawer

/**
 * AI Analyst: full-screen chat with user context.
 * Connects to POST /api/ai/chat
 */

import { useState, useRef, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Bot, Plus, Sparkles, ChevronDown } from "lucide-react";
import { toast } from "sonner";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChatMessageComponent, type ChatMessage } from "@/components/ai/ChatMessage";
import { TypingIndicator } from "@/components/ai/TypingIndicator";
import { PresetQuestions } from "@/components/ai/PresetQuestions";
import { ChatInput } from "@/components/ai/ChatInput";
import { aiApi } from "@/api/ai";

export function AIAnalystPage() {
  const { t } = useTranslation();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [chatHistory, setChatHistory] = useState<string[]>([]);
  const [sessionId, setSessionId] = useState<number | undefined>();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isTyping]);

  const handleSend = async (content: string, _presetKey?: string) => {
    const userMsg: ChatMessage = { role: "user", content, timestamp: Date.now() };
    setMessages((m) => [...m, userMsg]);
    setIsTyping(true);

    try {
      const { data } = await aiApi.chat({
        message: content,
        session_id: sessionId,
        context_type: "general",
      });
      setSessionId(data.session_id);
      const aiMsg: ChatMessage = {
        role: "assistant",
        content: data.response,
        timestamp: Date.now(),
      };
      setMessages((m) => [...m, aiMsg]);
      setChatHistory((h) => [content, ...h.slice(0, 9)]);
    } catch (err) {
      const msg =
        (err as { response?: { status?: number } })?.response?.status === 503
          ? t("ai.serviceUnavailable")
          : t("common.error");
      toast.error(msg);
      const fallbackMsg: ChatMessage = {
        role: "assistant",
        content: t("ai.serviceUnavailable"),
        timestamp: Date.now(),
      };
      setMessages((m) => [...m, fallbackMsg]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleNewChat = () => {
    setMessages([]);
    setIsTyping(false);
    setSessionId(undefined);
  };

  const handleCopy = () => {
    toast.success(t("common.copied"));
  };

  const isEmpty = messages.length === 0 && !isTyping;

  return (
    <div className="flex min-h-[50vh] h-[calc(100dvh-12rem)] max-h-[calc(100dvh-12rem)] flex-col overflow-hidden rounded-xl border border-border/50 bg-gradient-to-b from-background via-background to-muted/20 md:h-[calc(100vh-4rem)] md:max-h-[calc(100dvh-4rem)] dark:from-background dark:via-background dark:to-muted/10">
      {/* Header */}
      <header className="flex shrink-0 items-center justify-between gap-2 border-b border-border/50 px-3 py-3 sm:gap-4 sm:px-4">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10">
            <Bot className="size-5 text-primary" />
          </div>
          <div>
            <h1 className="flex items-center gap-2 font-semibold">
              {t("ai.title")}
              <Sparkles className="size-4 text-primary" />
            </h1>
            <Badge variant="secondary" className="text-xs">
              {t("ai.beta")}
            </Badge>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleNewChat}>
            <Plus className="mr-2 size-4" />
            {t("ai.newChat")}
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                {t("ai.chatHistory")}
                <ChevronDown className="ml-2 size-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-64">
              {chatHistory.length === 0 ? (
                <p className="px-3 py-4 text-sm text-muted-foreground">
                  {t("ai.noHistory")}
                </p>
              ) : (
                chatHistory.map((q, i) => (
                  <DropdownMenuItem
                    key={i}
                    onClick={() => handleSend(q, undefined)}
                    className="max-w-full truncate"
                  >
                    {q}
                  </DropdownMenuItem>
                ))
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      {/* Messages area */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-3 py-4 sm:px-4 sm:py-6"
      >
        <div className="mx-auto max-w-3xl space-y-6">
          {isEmpty ? (
            <div className="space-y-6">
              <p className="text-center text-sm text-muted-foreground">
                {t("ai.welcome")}
              </p>
              <PresetQuestions onSelect={handleSend} />
            </div>
          ) : (
            <>
              {messages.map((m, i) => (
                <ChatMessageComponent
                  key={`${m.timestamp}-${i}`}
                  message={m}
                  onCopy={handleCopy}
                />
              ))}
              {isTyping && (
                <div className="flex gap-3 animate-in fade-in-0 duration-200">
                  <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-primary/10">
                    <Bot className="size-6 text-primary" />
                  </div>
                  <div className="flex items-center rounded-2xl bg-card/80 px-4 py-3 backdrop-blur-sm">
                    <TypingIndicator />
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Input area */}
      <div className="shrink-0 border-t border-border/50 p-3 sm:p-4">
        <div className="mx-auto max-w-3xl">
          <ChatInput onSend={handleSend} disabled={isTyping} />
        </div>
      </div>
    </div>
  );
}
