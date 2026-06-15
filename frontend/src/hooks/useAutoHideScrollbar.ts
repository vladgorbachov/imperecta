/**
 * Auto-hiding overlay scrollbar manager.
 *
 * Native scrollbars stay hidden globally (see `index.css`); this hook computes
 * thumb size/position for an arbitrary scroll container and exposes show/hide
 * state plus pointer-drag bindings consumed by `Scrollable`.
 *
 * Behavior:
 * - Thumbs are invisible at rest, shown on scroll and on container hover.
 * - A 2s idle timer (reset on each scroll) hides them once the cursor is not
 *   over the container and no drag is in progress.
 * - Per axis, the thumb is enabled only when that axis actually overflows.
 * - Re-measures via `ResizeObserver` on the container and its first child.
 * - Reduced-motion is honored via CSS (the JS does not animate).
 */

import { useEffect, useRef, useState, type PointerEvent, type RefObject } from "react";

const HIDE_DELAY_MS = 2000;
const MIN_THUMB_SIZE = 24;
const OVERFLOW_EPSILON = 1;

export type ScrollableAxis = "y" | "x" | "both";

export interface ThumbMetric {
  /** Thumb length in px along the scroll axis. */
  size: number;
  /** Top (vertical) or left (horizontal) offset within the track, in px. */
  offset: number;
}

export interface ThumbState {
  visible: boolean;
  dragging: boolean;
  metric: ThumbMetric | null;
}

interface AutoHideScrollbarResult {
  vertical: ThumbState;
  horizontal: ThumbState;
  bindings: {
    vertical: { onPointerDown: (event: PointerEvent<HTMLDivElement>) => void };
    horizontal: { onPointerDown: (event: PointerEvent<HTMLDivElement>) => void };
  };
}

function computeMetric(
  scrollExtent: number,
  clientExtent: number,
  scrollPosition: number,
): ThumbMetric | null {
  if (scrollExtent <= clientExtent + OVERFLOW_EPSILON) {
    return null;
  }
  const ratio = clientExtent / scrollExtent;
  const size = Math.max(MIN_THUMB_SIZE, Math.round(clientExtent * ratio));
  const movableTrack = Math.max(0, clientExtent - size);
  const movableContent = Math.max(1, scrollExtent - clientExtent);
  const offset = Math.round((scrollPosition / movableContent) * movableTrack);
  return { size, offset };
}

export function useAutoHideScrollbar(
  scrollRef: RefObject<HTMLDivElement | null>,
  axis: ScrollableAxis = "y",
): AutoHideScrollbarResult {
  const wantVertical = axis === "y" || axis === "both";
  const wantHorizontal = axis === "x" || axis === "both";

  const [vertical, setVertical] = useState<ThumbState>({
    visible: false,
    dragging: false,
    metric: null,
  });
  const [horizontal, setHorizontal] = useState<ThumbState>({
    visible: false,
    dragging: false,
    metric: null,
  });

  const hoveringRef = useRef(false);
  const draggingRef = useRef<"v" | "h" | null>(null);
  const hideTimerRef = useRef<number | null>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;

    const measure = () => {
      if (wantVertical) {
        const metric = computeMetric(
          container.scrollHeight,
          container.clientHeight,
          container.scrollTop,
        );
        setVertical((prev) =>
          prev.metric?.size === metric?.size && prev.metric?.offset === metric?.offset
            ? prev
            : { ...prev, metric },
        );
      }
      if (wantHorizontal) {
        const metric = computeMetric(
          container.scrollWidth,
          container.clientWidth,
          container.scrollLeft,
        );
        setHorizontal((prev) =>
          prev.metric?.size === metric?.size && prev.metric?.offset === metric?.offset
            ? prev
            : { ...prev, metric },
        );
      }
    };

    const scheduleMeasure = () => {
      if (rafRef.current != null) return;
      rafRef.current = window.requestAnimationFrame(() => {
        rafRef.current = null;
        measure();
      });
    };

    const clearHideTimer = () => {
      if (hideTimerRef.current != null) {
        window.clearTimeout(hideTimerRef.current);
        hideTimerRef.current = null;
      }
    };

    const show = () => {
      if (wantVertical) setVertical((prev) => (prev.visible ? prev : { ...prev, visible: true }));
      if (wantHorizontal) {
        setHorizontal((prev) => (prev.visible ? prev : { ...prev, visible: true }));
      }
    };

    const hide = () => {
      setVertical((prev) => (prev.visible ? { ...prev, visible: false } : prev));
      setHorizontal((prev) => (prev.visible ? { ...prev, visible: false } : prev));
    };

    const scheduleHide = () => {
      clearHideTimer();
      hideTimerRef.current = window.setTimeout(() => {
        hideTimerRef.current = null;
        if (hoveringRef.current || draggingRef.current) return;
        hide();
      }, HIDE_DELAY_MS);
    };

    const onScroll = () => {
      scheduleMeasure();
      show();
      scheduleHide();
    };
    const onEnter = () => {
      hoveringRef.current = true;
      clearHideTimer();
      scheduleMeasure();
      show();
    };
    const onLeave = () => {
      hoveringRef.current = false;
      scheduleHide();
    };

    container.addEventListener("scroll", onScroll, { passive: true });
    container.addEventListener("mouseenter", onEnter);
    container.addEventListener("mouseleave", onLeave);

    const resizeObserver = new ResizeObserver(() => scheduleMeasure());
    resizeObserver.observe(container);
    const firstChild = container.firstElementChild;
    if (firstChild instanceof Element) {
      resizeObserver.observe(firstChild);
    }

    measure();

    return () => {
      container.removeEventListener("scroll", onScroll);
      container.removeEventListener("mouseenter", onEnter);
      container.removeEventListener("mouseleave", onLeave);
      resizeObserver.disconnect();
      clearHideTimer();
      if (rafRef.current != null) {
        window.cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [scrollRef, wantVertical, wantHorizontal]);

  const beginDrag = (kind: "v" | "h") => (event: PointerEvent<HTMLDivElement>) => {
    const container = scrollRef.current;
    if (!container) return;
    event.preventDefault();
    event.stopPropagation();

    const isVertical = kind === "v";
    const scrollExtent = isVertical ? container.scrollHeight : container.scrollWidth;
    const clientExtent = isVertical ? container.clientHeight : container.clientWidth;
    const startMetric = computeMetric(
      scrollExtent,
      clientExtent,
      isVertical ? container.scrollTop : container.scrollLeft,
    );
    if (startMetric == null) return;

    const startPointer = isVertical ? event.clientY : event.clientX;
    const startScroll = isVertical ? container.scrollTop : container.scrollLeft;
    const movableContent = Math.max(1, scrollExtent - clientExtent);
    const movableTrack = Math.max(1, clientExtent - startMetric.size);

    draggingRef.current = kind;
    if (isVertical) setVertical((prev) => ({ ...prev, dragging: true, visible: true }));
    else setHorizontal((prev) => ({ ...prev, dragging: true, visible: true }));

    const target = event.currentTarget;
    target.setPointerCapture(event.pointerId);

    const onMove = (moveEvent: globalThis.PointerEvent) => {
      const pointer = isVertical ? moveEvent.clientY : moveEvent.clientX;
      const next = startScroll + ((pointer - startPointer) * movableContent) / movableTrack;
      if (isVertical) container.scrollTop = next;
      else container.scrollLeft = next;
    };
    const onUp = (upEvent: globalThis.PointerEvent) => {
      try {
        target.releasePointerCapture(upEvent.pointerId);
      } catch {
        // pointer already released
      }
      target.removeEventListener("pointermove", onMove);
      target.removeEventListener("pointerup", onUp);
      target.removeEventListener("pointercancel", onUp);
      draggingRef.current = null;
      if (isVertical) setVertical((prev) => ({ ...prev, dragging: false }));
      else setHorizontal((prev) => ({ ...prev, dragging: false }));

      if (hideTimerRef.current != null) {
        window.clearTimeout(hideTimerRef.current);
      }
      hideTimerRef.current = window.setTimeout(() => {
        hideTimerRef.current = null;
        if (hoveringRef.current || draggingRef.current) return;
        setVertical((prev) => (prev.visible ? { ...prev, visible: false } : prev));
        setHorizontal((prev) => (prev.visible ? { ...prev, visible: false } : prev));
      }, HIDE_DELAY_MS);
    };

    target.addEventListener("pointermove", onMove);
    target.addEventListener("pointerup", onUp);
    target.addEventListener("pointercancel", onUp);
  };

  return {
    vertical,
    horizontal,
    bindings: {
      vertical: { onPointerDown: beginDrag("v") },
      horizontal: { onPointerDown: beginDrag("h") },
    },
  };
}
