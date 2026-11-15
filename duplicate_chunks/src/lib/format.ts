import type { DocStatus, DupType } from "./schema";

const nf = new Intl.NumberFormat("en-US");
export const fmt = (n: number) => nf.format(n);
export const pct = (n: number, d: number, digits = 1) => (d ? `${((100 * n) / d).toFixed(digits)}%` : "–");
export const ratio = (n: number, d: number) => (d ? n / d : 0);
export const score = (x: number) => x.toFixed(2);

export function chars(n: number): string {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M chars`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}k chars`;
  return `${n} chars`;
}

export function pages(p: number[]): string {
  if (!p.length) return "no page";
  const sorted = [...p].sort((a, b) => a - b);
  return sorted.length === 1 ? `p. ${sorted[0]}` : `pp. ${sorted[0]}–${sorted.at(-1)}`;
}

/** Document ids are long URL-derived slugs; show the most specific part. */
export function shortDoc(id: string): string {
  const parts = id.split("--");
  const last = parts.at(-1) ?? id;
  return last.length > 64 ? `${last.slice(0, 61)}…` : last;
}

export const TYPE_LABEL: Record<DupType, string> = {
  exact: "Exact",
  near: "Near",
  containment: "Containment",
};

export const TYPE_HELP: Record<DupType, string> = {
  exact: "Identical after normalizing case, whitespace and markdown",
  near: "Most 5-word phrases shared (Jaccard ≥ threshold)",
  containment: "The smaller chunk sits almost entirely inside the larger one",
};

export const STATUS_LABEL: Record<DocStatus, string> = {
  reviewed: "Reviewed",
  processed: "Processed",
  failed: "Failed",
  not_processed: "Not processed",
};
