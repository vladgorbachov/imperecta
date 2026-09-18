import { type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/* NOTE: no overflow on this wrapper — an overflow-auto div here becomes the
   sticky-header's scroll ancestor and kills `position: sticky` on thead th.
   Scrolling is owned by the surrounding <Scrollable> (or the page). */
const Table = ({ className, ...props }: HTMLAttributes<HTMLTableElement>) => (
  <div className="relative w-full">
    <table
      className={cn("w-full caption-bottom text-sm", className)}
      {...props}
    />
  </div>
);
Table.displayName = "Table";

const TableHeader = ({
  className,
  ...props
}: HTMLAttributes<HTMLTableSectionElement>) => (
  <thead className={cn("[&_tr]:border-b", className)} {...props} />
);
TableHeader.displayName = "TableHeader";

const TableBody = ({
  className,
  ...props
}: HTMLAttributes<HTMLTableSectionElement>) => (
  <tbody className={cn("[&_tr:last-child]:border-0", className)} {...props} />
);
TableBody.displayName = "TableBody";

const TableFooter = ({
  className,
  ...props
}: HTMLAttributes<HTMLTableSectionElement>) => (
  <tfoot
    className={cn(
      "border-t bg-muted/50 font-medium [&>tr]:last:border-b-0",
      className
    )}
    {...props}
  />
);
TableFooter.displayName = "TableFooter";

const TableRow = ({
  className,
  ...props
}: HTMLAttributes<HTMLTableRowElement>) => (
  <tr
    className={cn(
      "border-b transition-colors duration-150 hover:bg-[var(--glass-bg-hover)] data-[state=selected]:bg-[var(--accent-bg-subtle)]",
      className
    )}
    {...props}
  />
);
TableRow.displayName = "TableRow";

const TableHead = ({
  className,
  ...props
}: HTMLAttributes<HTMLTableCellElement>) => (
  <th
    className={cn(
      "h-8 px-3 text-left align-middle text-2xs font-medium text-muted-foreground [&:has([role=checkbox])]:pr-0",
      className
    )}
    {...props}
  />
);
TableHead.displayName = "TableHead";

const TableCell = ({
  className,
  colSpan,
  ...props
}: HTMLAttributes<HTMLTableCellElement> & { colSpan?: number }) => (
  <td
    colSpan={colSpan}
    className={cn("px-3 py-2 align-middle [&:has([role=checkbox])]:pr-0", className)}
    {...props}
  />
);
TableCell.displayName = "TableCell";

const TableCaption = ({
  className,
  ...props
}: HTMLAttributes<HTMLTableCaptionElement>) => (
  <caption
    className={cn("mt-4 text-sm text-muted-foreground", className)}
    {...props}
  />
);
TableCaption.displayName = "TableCaption";

export { Table, TableHeader, TableBody, TableFooter, TableHead, TableRow, TableCell, TableCaption };
