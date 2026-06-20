import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Terminal } from "lucide-react";
import { useParsingWorkerLogRelay } from "@/hooks/useAdmin";
import { cn } from "@/lib/utils";

/** Minimum visible rows when the buffer is short; viewport fits ~10 lines at leading-5. */
const VISIBLE_LINES = 10;

interface WorkerLogRelayPanelProps {
  jobId: string | null;
  enabled: boolean;
}

/**
 * Live tail of celery worker deploy logs (Redis relay), ~10 visible lines with scroll.
 */
export function WorkerLogRelayPanel({ jobId, enabled }: WorkerLogRelayPanelProps) {
  const { t } = useTranslation();
  const [cursor, setCursor] = useState(0);
  const [displayLines, setDisplayLines] = useState<string[]>([]);
  const [animating, setAnimating] = useState(false);
  const bufferRef = useRef<string[]>([]);
  const prevCountRef = useRef(0);

  const relayQuery = useParsingWorkerLogRelay(cursor, jobId, {
    enabled: enabled && Boolean(jobId),
    refetchInterval: 2000,
  });

  useEffect(() => {
    const incoming = relayQuery.data?.lines ?? [];
    if (incoming.length === 0) {
      return;
    }
    const nextCursor = relayQuery.data?.next_cursor ?? cursor;
    const newTexts = incoming.map((row) => row.line);
    bufferRef.current = [...bufferRef.current, ...newTexts].slice(-120);
    setCursor(nextCursor);
    setDisplayLines(bufferRef.current.slice(-VISIBLE_LINES));
    if (bufferRef.current.length > prevCountRef.current) {
      setAnimating(true);
      const timer = window.setTimeout(() => setAnimating(false), 280);
      prevCountRef.current = bufferRef.current.length;
      return () => window.clearTimeout(timer);
    }
    prevCountRef.current = bufferRef.current.length;
  }, [relayQuery.data]);

  useEffect(() => {
    if (!enabled || !jobId) {
      setCursor(0);
      setDisplayLines([]);
      bufferRef.current = [];
      prevCountRef.current = 0;
    }
  }, [enabled, jobId]);

  const padded =
    displayLines.length >= VISIBLE_LINES
      ? displayLines
      : [
          ...Array.from({ length: VISIBLE_LINES - displayLines.length }, () => ""),
          ...displayLines,
        ];

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
        <Terminal className="size-4" />
        {t("admin.dataCollection.workerLogRelay")}
      </div>
      <div
        className={cn(
          "overflow-hidden rounded-md border bg-zinc-950 px-3 py-2 font-mono text-xs leading-5 text-emerald-400",
          "[.light_&]:bg-[#0b2447] [.light_&]:text-sky-100 [.light_&]:border-[#13315c]",
          animating && "ring-1 ring-emerald-500/40 [.light_&]:ring-sky-400/40",
        )}
        aria-live="polite"
        aria-label={t("admin.dataCollection.workerLogRelay")}
      >
        <div className="max-h-[13.625rem] overflow-y-auto">
          <div
            className={cn(
              "flex flex-col gap-0.5 transition-transform duration-300 ease-out",
              animating && "-translate-y-0.5",
            )}
          >
            {padded.map((line, index) => (
              <div
                key={`${index}-${line.slice(0, 24)}-${bufferRef.current.length}`}
                className={cn(
                  "truncate whitespace-nowrap",
                  !line && "text-zinc-600 [.light_&]:text-sky-300/60",
                  line && index === padded.length - 1 && animating && "text-emerald-300 [.light_&]:text-sky-50",
                )}
              >
                {line || t("admin.dataCollection.workerLogRelayWaiting")}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
