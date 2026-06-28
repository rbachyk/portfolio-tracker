import { AlertTriangle, ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Inbox } from "lucide-react";
import { ButtonHTMLAttributes, isValidElement, ReactNode, useEffect, useMemo, useState } from "react";

import { Sign } from "./format";

// ---------------------------------------------------------------------------
// Async resource state
// ---------------------------------------------------------------------------
export type Resource<T> = {
  data: T | null;
  error: string | null;
  isLoading: boolean;
};

export function DataState<T>({
  resource,
  children,
  skeleton,
}: {
  resource: Resource<T>;
  children: (data: T) => ReactNode;
  skeleton?: ReactNode;
}) {
  if (resource.isLoading && !resource.data) {
    return <>{skeleton ?? <SkeletonStack />}</>;
  }
  if (resource.error && !resource.data) {
    return (
      <div className="state-block error" role="alert">
        <AlertTriangle size={18} />
        <span>{resource.error}</span>
      </div>
    );
  }
  if (!resource.data) {
    return <EmptyState message="No data available." />;
  }
  return <>{children(resource.data)}</>;
}

// ---------------------------------------------------------------------------
// Layout primitives
// ---------------------------------------------------------------------------
export function Panel({
  title,
  subtitle,
  action,
  children,
  className,
  bare,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bare?: boolean;
}) {
  return (
    <section className={`panel${className ? ` ${className}` : ""}`}>
      {title || action ? (
        <header className="panel-head">
          <div className="panel-head-text">
            {title ? <h2>{title}</h2> : null}
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
          {action ? <div className="panel-head-action">{action}</div> : null}
        </header>
      ) : null}
      <div className={bare ? "panel-body bare" : "panel-body"}>{children}</div>
    </section>
  );
}

export function StatTile({
  label,
  value,
  unit,
  delta,
  sign,
  hint,
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  delta?: ReactNode;
  sign?: Sign;
  hint?: string;
}) {
  return (
    <div className="stat-tile">
      <span className="stat-label">{label}</span>
      <div className="stat-value-row">
        <strong className={sign ? `stat-value pnl-${sign}` : "stat-value"}>{value}</strong>
        {unit ? <span className="stat-unit">{unit}</span> : null}
      </div>
      {delta ? <span className={sign ? `stat-delta pnl-${sign}` : "stat-delta"}>{delta}</span> : null}
      {hint ? <span className="stat-hint">{hint}</span> : null}
    </div>
  );
}

export function Badge({
  tone = "neutral",
  children,
}: {
  tone?: "neutral" | "pos" | "neg" | "warn" | "info" | "brand";
  children: ReactNode;
}) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "icon";
};

export function Button({ variant = "secondary", className, children, ...rest }: ButtonProps) {
  return (
    <button className={`btn btn-${variant}${className ? ` ${className}` : ""}`} {...rest}>
      {children}
    </button>
  );
}

export function ProgressBar({ value, max }: { value: number; max: number }) {
  const ratio = max > 0 ? Math.min(Math.max(value / max, 0), 1) : 0;
  return (
    <div className="progress-cell">
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${ratio * 100}%` }} />
      </div>
      <span className="progress-count">
        {value} / {max}
      </span>
    </div>
  );
}

export function EmptyState({ title, message }: { title?: string; message: string }) {
  return (
    <div className="state-block empty">
      <Inbox size={18} />
      <div>
        {title ? <strong>{title}</strong> : null}
        <span>{message}</span>
      </div>
    </div>
  );
}

export function SkeletonStack({ rows = 3 }: { rows?: number }) {
  return (
    <div className="skeleton-stack" aria-hidden="true">
      {Array.from({ length: rows }).map((_, index) => (
        <div className="skeleton-line" key={index} style={{ width: `${100 - index * 12}%` }} />
      ))}
    </div>
  );
}

export function ChartSkeleton({ height = 240 }: { height?: number }) {
  return <div className="skeleton-chart" style={{ height }} aria-hidden="true" />;
}

// ---------------------------------------------------------------------------
// Tables (sortable + paginated)
// ---------------------------------------------------------------------------
type SortValue = string | number | null | undefined;

export type TableRow = {
  key: string;
  cells: ReactNode[];
  sortValues?: SortValue[];
};

export type Column = string | { label: string; align?: "right" | "center" };

function columnLabel(column: Column): string {
  return typeof column === "string" ? column : column.label;
}

function columnAlign(column: Column): "right" | "center" | undefined {
  return typeof column === "string" ? undefined : column.align;
}

export function SortableTable({
  columns,
  rows,
  pageSize,
  caption,
}: {
  columns: Column[];
  rows: TableRow[];
  pageSize?: number;
  caption?: string;
}) {
  const [sort, setSort] = useState<{ index: number; direction: "asc" | "desc" } | null>(null);
  const [page, setPage] = useState(1);

  const sortedRows = useMemo(() => {
    if (!sort) return rows;
    const valueFor = (row: TableRow) => {
      const explicit = row.sortValues?.[sort.index];
      if (explicit !== undefined && explicit !== null) return explicit;
      return nodeText(row.cells[sort.index]);
    };
    return [...rows].sort((left, right) => {
      const leftValue = normalizeSortValue(valueFor(left));
      const rightValue = normalizeSortValue(valueFor(right));
      const result =
        typeof leftValue === "number" && typeof rightValue === "number"
          ? leftValue - rightValue
          : String(leftValue).localeCompare(String(rightValue), undefined, {
              numeric: true,
              sensitivity: "base",
            });
      return sort.direction === "asc" ? result : -result;
    });
  }, [rows, sort]);

  const totalPages = pageSize ? Math.max(Math.ceil(sortedRows.length / pageSize), 1) : 1;
  const safePage = Math.min(page, totalPages);
  const visibleRows = pageSize
    ? sortedRows.slice((safePage - 1) * pageSize, safePage * pageSize)
    : sortedRows;

  useEffect(() => {
    setPage(1);
  }, [rows.length, pageSize, sort?.index, sort?.direction]);

  function toggleSort(index: number) {
    setSort((current) => {
      if (!current || current.index !== index) return { index, direction: "asc" };
      if (current.direction === "asc") return { index, direction: "desc" };
      return null;
    });
  }

  return (
    <>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {columns.map((column, index) => {
                const label = columnLabel(column);
                const align = columnAlign(column);
                const isSorted = sort?.index === index;
                return (
                  <th key={label} className={align ? `align-${align}` : undefined}>
                    <button
                      className={`sort-button${isSorted ? " is-sorted" : ""}`}
                      onClick={() => toggleSort(index)}
                      title={`Sort by ${label}`}
                      type="button"
                    >
                      <span>{label}</span>
                      {isSorted ? (
                        sort.direction === "asc" ? (
                          <ArrowUp size={13} />
                        ) : (
                          <ArrowDown size={13} />
                        )
                      ) : null}
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {visibleRows.length === 0 ? (
              <tr>
                <td className="table-empty" colSpan={columns.length}>
                  No records
                </td>
              </tr>
            ) : (
              visibleRows.map((row) => (
                <tr key={row.key}>
                  {row.cells.map((cell, cellIndex) => (
                    <td
                      key={`${row.key}-${cellIndex}`}
                      className={columnAlign(columns[cellIndex]) ? `align-${columnAlign(columns[cellIndex])}` : undefined}
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <div className="table-footer">
        {caption ? <span className="table-caption">{caption}</span> : <span />}
        {pageSize && sortedRows.length > pageSize ? (
          <div className="pagination">
            <Button
              variant="icon"
              disabled={safePage <= 1}
              onClick={() => setPage((value) => Math.max(value - 1, 1))}
              title="Previous page"
            >
              <ChevronLeft size={16} />
            </Button>
            <span>
              {safePage} / {totalPages}
            </span>
            <Button
              variant="icon"
              disabled={safePage >= totalPages}
              onClick={() => setPage((value) => Math.min(value + 1, totalPages))}
              title="Next page"
            >
              <ChevronRight size={16} />
            </Button>
          </div>
        ) : null}
      </div>
    </>
  );
}

export function SimpleTable({
  columns,
  rows,
  pageSize,
  caption,
}: {
  columns: Column[];
  rows: ReactNode[][];
  pageSize?: number;
  caption?: string;
}) {
  return (
    <SortableTable
      columns={columns}
      pageSize={pageSize}
      caption={caption}
      rows={rows.map((row, rowIndex) => ({
        key: `${rowIndex}-${row.map(nodeText).join("|")}`,
        cells: row,
      }))}
    />
  );
}

/** Extract sortable/searchable plain text from any cell node. */
function nodeText(node: ReactNode): string {
  if (node === null || node === undefined || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(nodeText).join(" ");
  if (isValidElement(node)) return nodeText((node.props as { children?: ReactNode }).children);
  return "";
}

function normalizeSortValue(value: SortValue): string | number {
  if (value === null || value === undefined || value === "N/A" || value === "Never" || value === "—") {
    return "";
  }
  if (typeof value === "number") return Number.isFinite(value) ? value : "";
  const trimmed = String(value).trim();
  if (!trimmed) return "";
  const numeric = Number(trimmed.replaceAll(",", "").replace("%", "").replace("+", ""));
  if (Number.isFinite(numeric)) return numeric;
  const timestamp = Date.parse(trimmed);
  if (Number.isFinite(timestamp)) return timestamp;
  return trimmed;
}
