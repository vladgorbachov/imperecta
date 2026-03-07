/**
 * AI Analyst: full-screen chat with user context.
 * TODO: connect to POST /api/ai/chat { messages, context }
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

/** Mock AI responses keyed by preset i18n key. */
const MOCK_RESPONSES: Record<string, string> = {
  "ai.preset1": `## Top 3 Underpriced Products

Based on competitor and market analysis:

| Product | Current | Recommended | Potential |
|---------|---------|-------------|-----------|
| Smartphone X | 45,000 ₽ | 48,500 ₽ | +7.8% |
| Headphones Y | 12,900 ₽ | 14,200 ₽ | +10.1% |
| Tablet Z | 28,500 ₽ | 30,000 ₽ | +5.3% |

**Recommendation:** Raise prices 5–7% over 2 weeks. Competitors maintain higher levels.`,
  "ai.preset2": `## Margin vs Market

**Your avg margin:** ~23.5%  
**Market avg:** ~18.2%

You are **5.3 pp above market** — good for premium positioning.

- **Electronics:** you 21%, market 15%
- **Accessories:** you 28%, market 22%

**Risk:** increased competition may shift buyers to cheaper options.`,
  "ai.preset3": `## Scenario: Competitor −15%

**Options:**

1. **No reaction** — if market share is stable, hold price
2. **Partial cut** — −5–7% on key SKUs
3. **Promo** — temporary discount instead of permanent cut

**Recommendation:** Cut 5% only on top 3 competing products. Full match would erode margin.`,
  "ai.preset4": `## +10% Volume Simulation

At current prices:

| Metric | Now | After +10% |
|--------|-----|------------|
| Revenue | 2.4M ₽ | 2.64M ₽ |
| Margin | 23.5% | 22.1% |
| Logistics | 8% | 7.2% |

**Conclusion:** +10% volume yields +9.2% revenue with modest margin pressure. Feasible with current stock.`,
  "ai.preset5": `## Analysis: Competitor X Raised Price

Possible reasons:

- **Cost** — higher procurement prices
- **Demand** — testing price elasticity
- **Positioning** — moving to premium
- **Assortment** — phasing out cheap SKUs

**Action:** Monitor 1–2 weeks. If X's volume drops — no need to react.`,
  "ai.preset6": `## Weekly Risks

1. **Ozon** — promo on 12% of products, possible outflow
2. **WB** — cuts on gadgets up to −8%
3. **Stock** — 3 products low on inventory

**Priority:** Update prices on top 5 products by Wednesday.`,
};

function getMockResponse(userMessage: string, presetKey?: string): string {
  const key = presetKey ?? userMessage;
  return (
    MOCK_RESPONSES[key] ??
    `Based on your data: **${userMessage}** — this is an important question. I recommend analyzing trends over the last 7 days and comparing with competitors.`
  );
}

export function AIAnalystPage() {
  const { t } = useTranslation();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [chatHistory, setChatHistory] = useState<string[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isTyping]);

  const handleSend = (content: string, presetKey?: string) => {
    const userMsg: ChatMessage = { role: "user", content, timestamp: Date.now() };
    setMessages((m) => [...m, userMsg]);
    setIsTyping(true);

    setTimeout(() => {
      const aiContent = getMockResponse(content, presetKey);
      const aiMsg: ChatMessage = { role: "assistant", content: aiContent, timestamp: Date.now() };
      setMessages((m) => [...m, aiMsg]);
      setChatHistory((h) => [content, ...h.slice(0, 9)]);
      setIsTyping(false);
    }, 2000);
  };

  const handleNewChat = () => {
    setMessages([]);
    setIsTyping(false);
  };

  const handleCopy = () => {
    toast.success(t("common.copied"));
  };

  const isEmpty = messages.length === 0 && !isTyping;

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col overflow-hidden rounded-xl border border-border/50 bg-gradient-to-b from-background via-background to-muted/20 dark:from-background dark:via-background dark:to-muted/10">
      {/* Header */}
      <header className="flex shrink-0 items-center justify-between gap-4 border-b border-border/50 px-4 py-3">
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
        className="flex-1 overflow-y-auto px-4 py-6"
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
      <div className="shrink-0 border-t border-border/50 p-4">
        <div className="mx-auto max-w-3xl">
          <ChatInput onSend={handleSend} disabled={isTyping} />
        </div>
      </div>
    </div>
  );
}
