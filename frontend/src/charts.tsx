import { useEffect, useId, useMemo, useRef, useState } from "react";

import { fmtCompact } from "./format";

// ---------------------------------------------------------------------------
// Categorical palette for allocation segments. Tuned to read on both themes.
// USDT / cash assets are pinned to the Binance gold so they're recognisable.
// ---------------------------------------------------------------------------
export const ASSET_PALETTE = [
  "#16c784",
  "#3b82f6",
  "#a855f7",
  "#ec4899",
  "#f97316",
  "#06b6d4",
  "#eab308",
  "#ef4444",
  "#14b8a6",
  "#8b5cf6",
];
export const CASH_COLOR = "#f0b90b";
export const OTHERS_COLOR = "#64748b";

function useMeasure<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) setWidth(entry.contentRect.width);
    });
    observer.observe(el);
    setWidth(el.getBoundingClientRect().width);
    return () => observer.disconnect();
  }, []);
  return { ref, width };
}

function ChartEmpty({ height, label }: { height: number; label: string }) {
  return (
    <div className="chart-empty" style={{ height }}>
      {label}
    </div>
  );
}

// ---------------------------------------------------------------------------
// AreaChart — gradient area + line with hover crosshair and tooltip.
// ---------------------------------------------------------------------------
export type SeriesPoint = { x: string; y: number };

export function AreaChart({
  data,
  height = 240,
  color = "var(--brand)",
  formatX = (value: string) => value,
  formatY = (value: number) => fmtCompact(value),
  emptyLabel = "No data yet",
  bare = false,
}: {
  data: SeriesPoint[];
  height?: number;
  color?: string;
  formatX?: (value: string) => string;
  formatY?: (value: number) => string;
  emptyLabel?: string;
  bare?: boolean;
}) {
  const { ref, width } = useMeasure<HTMLDivElement>();
  const gradientId = useId().replace(/:/g, "");
  const [hover, setHover] = useState<number | null>(null);

  const geometry = useMemo(() => {
    if (data.length === 0 || width === 0) return null;
    const padT = 10;
    const padB = bare ? 6 : 22;
    const plotH = Math.max(height - padT - padB, 1);
    const values = data.map((point) => point.y);
    let min = Math.min(...values);
    let max = Math.max(...values);
    if (min === max) {
      const pad = Math.abs(min) || 1;
      min -= pad;
      max += pad;
    } else {
      const headroom = (max - min) * 0.08;
      min -= headroom;
      max += headroom;
    }
    const span = max - min || 1;
    const xFor = (index: number) =>
      data.length === 1 ? width / 2 : (index / (data.length - 1)) * width;
    const yFor = (value: number) => padT + (1 - (value - min) / span) * plotH;
    const linePoints = data.map((point, index) => `${xFor(index)},${yFor(point.y)}`);
    const areaPath = `M0,${height - padB} L${linePoints.join(" L")} L${width},${height - padB} Z`;
    return { padB, xFor, yFor, linePoints, areaPath };
  }, [data, width, height, bare]);

  if (data.length === 0) return <ChartEmpty height={height} label={emptyLabel} />;

  function handleMove(event: React.MouseEvent<HTMLDivElement>) {
    if (width === 0 || data.length === 0) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const index = Math.round((x / width) * (data.length - 1));
    setHover(Math.min(Math.max(index, 0), data.length - 1));
  }

  const hoverPoint = hover !== null && geometry ? data[hover] : null;
  const hoverX = hover !== null && geometry ? geometry.xFor(hover) : 0;
  const hoverY = hoverPoint && geometry ? geometry.yFor(hoverPoint.y) : 0;
  const tooltipLeft = width ? Math.min(Math.max(hoverX, 64), width - 64) : 0;

  return (
    <div
      className="chart"
      ref={ref}
      style={{ height }}
      onMouseMove={handleMove}
      onMouseLeave={() => setHover(null)}
    >
      {geometry ? (
        <svg width={width} height={height} role="img" aria-label="Time series chart">
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.28} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <path d={geometry.areaPath} fill={`url(#${gradientId})`} />
          <polyline
            points={geometry.linePoints.join(" ")}
            fill="none"
            stroke={color}
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
          {hoverPoint ? (
            <g>
              <line
                x1={hoverX}
                y1={6}
                x2={hoverX}
                y2={height - geometry.padB}
                className="chart-crosshair"
              />
              <circle cx={hoverX} cy={hoverY} r={4.5} fill={color} className="chart-dot" />
            </g>
          ) : null}
        </svg>
      ) : null}
      {hoverPoint ? (
        <div className="chart-tooltip" style={{ left: tooltipLeft }}>
          <span className="chart-tooltip-value">{formatY(hoverPoint.y)}</span>
          <span className="chart-tooltip-label">{formatX(hoverPoint.x)}</span>
        </div>
      ) : null}
      {!bare && data.length > 1 ? (
        <div className="chart-axis">
          <span>{formatX(data[0].x)}</span>
          <span>{formatX(data[data.length - 1].x)}</span>
        </div>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// DonutChart — interactive ring with center readout and synced legend.
// ---------------------------------------------------------------------------
export type DonutSlice = { label: string; value: number; color: string };

function polar(cx: number, cy: number, r: number, angle: number) {
  return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
}

function arcPath(cx: number, cy: number, rOuter: number, rInner: number, start: number, end: number) {
  const largeArc = end - start > Math.PI ? 1 : 0;
  const p1 = polar(cx, cy, rOuter, start);
  const p2 = polar(cx, cy, rOuter, end);
  const p3 = polar(cx, cy, rInner, end);
  const p4 = polar(cx, cy, rInner, start);
  return [
    `M ${p1.x} ${p1.y}`,
    `A ${rOuter} ${rOuter} 0 ${largeArc} 1 ${p2.x} ${p2.y}`,
    `L ${p3.x} ${p3.y}`,
    `A ${rInner} ${rInner} 0 ${largeArc} 0 ${p4.x} ${p4.y}`,
    "Z",
  ].join(" ");
}

export function DonutChart({
  slices,
  size = 180,
  thickness = 26,
  centerLabel,
  formatValue = (value: number) => fmtCompact(value),
}: {
  slices: DonutSlice[];
  size?: number;
  thickness?: number;
  centerLabel?: string;
  formatValue?: (value: number) => string;
}) {
  const [active, setActive] = useState<number | null>(null);
  const total = slices.reduce((sum, slice) => sum + Math.max(slice.value, 0), 0);

  if (total <= 0) {
    return (
      <div className="donut-wrap">
        <ChartEmpty height={size} label="No allocation data" />
      </div>
    );
  }

  const cx = size / 2;
  const cy = size / 2;
  const rOuter = size / 2;
  const rInner = size / 2 - thickness;
  let cursor = -Math.PI / 2;
  const segments = slices.map((slice, index) => {
    const fraction = Math.max(slice.value, 0) / total;
    const start = cursor;
    const end = cursor + fraction * Math.PI * 2;
    cursor = end;
    return { slice, index, fraction, start, end };
  });

  const focused = active !== null ? segments[active] : null;
  const centerValue = focused ? focused.slice.value : total;
  const centerCaption = focused ? focused.slice.label : centerLabel ?? "Total";

  return (
    <div className="donut-wrap">
      <div className="donut-figure" style={{ width: size, height: size }}>
        <svg width={size} height={size} role="img" aria-label="Allocation breakdown">
          {segments.map((segment) => {
            const isFull = segment.fraction >= 0.9999;
            const dim = active !== null && active !== segment.index;
            return (
              <path
                key={segment.slice.label}
                d={
                  isFull
                    ? arcPath(cx, cy, rOuter, rInner, segment.start, segment.start + Math.PI * 1.9999)
                    : arcPath(cx, cy, rOuter, rInner, segment.start, segment.end)
                }
                fill={segment.slice.color}
                opacity={dim ? 0.35 : 1}
                className="donut-segment"
                onMouseEnter={() => setActive(segment.index)}
                onMouseLeave={() => setActive(null)}
              />
            );
          })}
        </svg>
        <div className="donut-center">
          <strong>{formatValue(centerValue)}</strong>
          <span>{centerCaption}</span>
          {focused ? <em>{(focused.fraction * 100).toFixed(1)}%</em> : null}
        </div>
      </div>
      <ul className="donut-legend">
        {segments.map((segment) => (
          <li
            key={segment.slice.label}
            className={active === segment.index ? "active" : undefined}
            onMouseEnter={() => setActive(segment.index)}
            onMouseLeave={() => setActive(null)}
          >
            <span className="legend-swatch" style={{ background: segment.slice.color }} />
            <span className="legend-label">{segment.slice.label}</span>
            <span className="legend-pct">{(segment.fraction * 100).toFixed(1)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------
// DivergingBars — horizontal bars from a center axis (e.g. PnL by symbol).
// ---------------------------------------------------------------------------
export function DivergingBars({
  data,
  formatValue = (value: number) => fmtCompact(value),
  limit = 12,
}: {
  data: Array<{ label: string; value: number }>;
  formatValue?: (value: number) => string;
  limit?: number;
}) {
  const visible = data.slice(0, limit);
  if (visible.length === 0) return <ChartEmpty height={180} label="No data" />;
  const max = Math.max(...visible.map((point) => Math.abs(point.value)), 1);
  return (
    <div className="diverging">
      {visible.map((point) => {
        const ratio = (Math.abs(point.value) / max) * 50;
        const positive = point.value >= 0;
        return (
          <div className="diverging-row" key={point.label}>
            <span className="diverging-label">{point.label}</span>
            <div className="diverging-track">
              <span className="diverging-axis" />
              <span
                className={positive ? "diverging-bar pos" : "diverging-bar neg"}
                style={
                  positive
                    ? { left: "50%", width: `${ratio}%` }
                    : { right: "50%", width: `${ratio}%` }
                }
              />
            </div>
            <strong className={positive ? "pnl-pos" : "pnl-neg"}>{formatValue(point.value)}</strong>
          </div>
        );
      })}
    </div>
  );
}
