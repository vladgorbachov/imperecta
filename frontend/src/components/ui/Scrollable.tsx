/**
 * Scrollable: thin wrapper around an overflowing div that renders an
 * auto-hiding overlay scrollbar on top of it (see `useAutoHideScrollbar`).
 *
 * Layout contract:
 * - Outer wrapper: `position: relative`. Caller may pass `outerClassName` to
 *   shape it (e.g. `absolute inset-0 h-full w-full`); by default it follows
 *   block flow and matches the inner scroll container's bounding box.
 * - Inner scroll container: receives `className`, `style`, and any other div
 *   props. The caller is responsible for the `overflow-*` rules that make it
 *   scroll (same as before adoption — only the visual scrollbar changes).
 * - Thumbs are absolute children of the outer wrapper and never affect layout.
 */

import { useRef, type HTMLAttributes } from "react";
import { useAutoHideScrollbar, type ScrollableAxis } from "@/hooks/useAutoHideScrollbar";
import { cn } from "@/lib/utils";

export interface ScrollableProps extends HTMLAttributes<HTMLDivElement> {
  axis?: ScrollableAxis;
  /** Extra classes for the relative outer wrapper. */
  outerClassName?: string;
}

export function Scrollable({
  axis = "y",
  outerClassName,
  className,
  children,
  ...rest
}: ScrollableProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const { vertical, horizontal, bindings } = useAutoHideScrollbar(scrollRef, axis);

  const showVertical = (axis === "y" || axis === "both") && vertical.metric != null;
  const showHorizontal = (axis === "x" || axis === "both") && horizontal.metric != null;

  return (
    <div className={cn("relative", outerClassName)}>
      <div ref={scrollRef} className={className} {...rest}>
        {children}
      </div>
      {showVertical && vertical.metric != null && (
        <div
          className="imp-scroll-thumb"
          data-visible={vertical.visible || vertical.dragging || undefined}
          data-dragging={vertical.dragging || undefined}
          style={{
            right: 2,
            width: 6,
            top: vertical.metric.offset,
            height: vertical.metric.size,
          }}
          onPointerDown={bindings.vertical.onPointerDown}
        />
      )}
      {showHorizontal && horizontal.metric != null && (
        <div
          className="imp-scroll-thumb"
          data-visible={horizontal.visible || horizontal.dragging || undefined}
          data-dragging={horizontal.dragging || undefined}
          style={{
            bottom: 2,
            height: 6,
            left: horizontal.metric.offset,
            width: horizontal.metric.size,
          }}
          onPointerDown={bindings.horizontal.onPointerDown}
        />
      )}
    </div>
  );
}
