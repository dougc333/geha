import { type ReactNode, useState } from "react";
import { STATUS_LABEL, TYPE_HELP, TYPE_LABEL } from "../lib/format";
import type { DocStatus, DupType, Verdict } from "../lib/schema";

export function Card({
  title,
  subtitle,
  actions,
  children,
  className = "",
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-xl border border-line bg-surface ${className}`}>
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-2 border-b border-line px-4 py-3">
          <div className="min-w-0">
            {title && <h2 className="text-sm font-semibold text-ink">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

export const TYPE_BG: Record<DupType, string> = {
  exact: "bg-exact",
  near: "bg-near",
  containment: "bg-containment",
};

export function TypeBadge({ type }: { type: DupType }) {
  return (
    <span
      title={TYPE_HELP[type]}
      className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface-2 px-2 py-0.5 text-[11px] font-medium text-ink-2"
    >
      <span className={`size-2 rounded-full ${TYPE_BG[type]}`} aria-hidden />
      {TYPE_LABEL[type]}
    </span>
  );
}

const STATUS_STYLE: Record<DocStatus, { icon: string; dot: string }> = {
  reviewed: { icon: "✓", dot: "text-good" },
  processed: { icon: "●", dot: "text-accent" },
  failed: { icon: "!", dot: "text-critical" },
  not_processed: { icon: "○", dot: "text-muted" },
};

export function StatusBadge({ status }: { status: DocStatus }) {
  const s = STATUS_STYLE[status];
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-xs text-ink-2">
      <span className={`w-3 text-center font-bold ${s.dot}`} aria-hidden>
        {s.icon}
      </span>
      {STATUS_LABEL[status]}
    </span>
  );
}

export function NumbersFlag({ compact = false }: { compact?: boolean }) {
  return (
    <span
      title="The chunks contain different numbers (amounts, percentages, years). Check before treating them as duplicates."
      className="inline-flex items-center gap-1 rounded-full bg-warning/20 px-2 py-0.5 text-[11px] font-medium text-ink"
    >
      <span aria-hidden>⚠</span>
      {compact ? "Figures" : "Figures differ"}
    </span>
  );
}

const VERDICT_STYLE: Record<Verdict, { label: string; icon: string; cls: string }> = {
  duplicate: { label: "Duplicate", icon: "✓", cls: "text-good" },
  distinct: { label: "Not duplicate", icon: "✕", cls: "text-critical" },
  unsure: { label: "Unsure", icon: "?", cls: "text-serious" },
};

export function VerdictBadge({ verdict }: { verdict?: Verdict }) {
  if (!verdict) return <span className="text-[11px] text-muted">Unreviewed</span>;
  const v = VERDICT_STYLE[verdict];
  return (
    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-ink-2">
      <span className={`font-bold ${v.cls}`} aria-hidden>
        {v.icon}
      </span>
      {v.label}
    </span>
  );
}
export { VERDICT_STYLE };

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: ReactNode }[];
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg border border-line bg-surface-2 p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
            value === o.value ? "bg-surface text-ink shadow-sm" : "text-ink-2 hover:text-ink"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Select({
  value,
  onChange,
  label,
  children,
}: {
  value: string;
  onChange: (v: string) => void;
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="inline-flex items-center gap-1.5 text-xs text-ink-2">
      <span>{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-md border border-line bg-surface px-2 py-1 text-xs text-ink"
      >
        {children}
      </select>
    </label>
  );
}

export function SearchBox({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
}) {
  return (
    <input
      type="search"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      aria-label={placeholder}
      className="w-full min-w-0 rounded-md border border-line bg-surface px-2.5 py-1.5 text-xs text-ink placeholder:text-muted"
    />
  );
}

export function Stat({
  label,
  value,
  detail,
  emphasis = false,
}: {
  label: string;
  value: ReactNode;
  detail?: ReactNode;
  emphasis?: boolean;
}) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4">
      <div className="text-xs font-medium text-ink-2">{label}</div>
      <div className={`mt-1 font-semibold tracking-tight text-ink ${emphasis ? "text-4xl" : "text-2xl"}`}>{value}</div>
      {detail && <div className="mt-1 text-xs text-muted">{detail}</div>}
    </div>
  );
}

/** Thin horizontal meter, e.g. share of pages visually verified. */
export function Meter({ value, className = "bg-accent" }: { value: number; className?: string }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
      <div className={`h-full rounded-full ${className}`} style={{ width: `${Math.min(100, Math.max(0, value * 100))}%` }} />
    </div>
  );
}

export type BarDatum = {
  key: string;
  label: ReactNode;
  value: number;
  display: string;
  tooltip: ReactNode;
  colorClass?: string;
  onClick?: () => void;
};

/** Horizontal bar chart: baseline at zero, thin bars, value labels in text
 * ink, a hover tooltip per bar. */
export function HBarChart({ data, max, ariaLabel }: { data: BarDatum[]; max?: number; ariaLabel: string }) {
  const [hover, setHover] = useState<string | null>(null);
  const top = max ?? Math.max(1e-9, ...data.map((d) => d.value));
  return (
    <div role="list" aria-label={ariaLabel} className="space-y-1">
      {data.map((d) => {
        const Row = d.onClick ? "button" : "div";
        return (
          <Row
            key={d.key}
            role="listitem"
            onClick={d.onClick}
            onMouseEnter={() => setHover(d.key)}
            onMouseLeave={() => setHover(null)}
            onFocus={() => setHover(d.key)}
            onBlur={() => setHover(null)}
            className={`group relative grid w-full grid-cols-[minmax(0,9rem)_1fr_4.5rem] items-center gap-3 rounded-md px-1 py-1 text-left ${
              d.onClick ? "cursor-pointer hover:bg-surface-2" : ""
            }`}
          >
            <span className="truncate text-xs text-ink-2">{d.label}</span>
            <span className="relative h-3">
              <span
                className={`absolute inset-y-0 left-0 rounded-r-[4px] ${d.colorClass ?? "bg-accent"} ${
                  hover && hover !== d.key ? "opacity-50" : ""
                }`}
                style={{ width: `${Math.max(d.value > 0 ? 0.6 : 0, (100 * d.value) / top)}%` }}
              />
            </span>
            <span className="text-right text-xs font-medium text-ink">{d.display}</span>
            {hover === d.key && (
              <span
                role="tooltip"
                className="pointer-events-none absolute top-full left-36 z-20 mt-1 w-max max-w-xs rounded-lg border border-line bg-surface px-3 py-2 text-xs text-ink shadow-lg"
              >
                {d.tooltip}
              </span>
            )}
          </Row>
        );
      })}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="px-4 py-10 text-center text-sm text-muted">{children}</div>;
}
