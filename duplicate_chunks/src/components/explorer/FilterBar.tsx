import { TYPE_LABEL } from "../../lib/format";
import { DupType } from "../../lib/schema";
import { DEFAULT_FILTERS, useStore } from "../../store/useStore";
import { useFilteredClusters } from "../../hooks/useQueue";
import { SearchBox, Segmented, Select, TYPE_BG } from "../ui";

export default function FilterBar() {
  const f = useStore((s) => s.filters);
  const setFilters = useStore((s) => s.setFilters);
  const families = useStore((s) => s.report!.families);
  const total = useStore((s) => s.report!.clusters.length);
  const { clusters, queue } = useFilteredClusters();
  const toggleType = (t: DupType) => {
    const next = f.types.includes(t) ? f.types.filter((x) => x !== t) : [...f.types, t];
    setFilters({ types: next.length ? next : [t] });
  };
  const changed = JSON.stringify(f) !== JSON.stringify(DEFAULT_FILTERS);
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-line bg-surface px-3 py-2">
      <div className="flex items-center gap-1" role="group" aria-label="Duplicate types">
        {DupType.options.map((t) => (
          <button
            key={t}
            aria-pressed={f.types.includes(t)}
            onClick={() => toggleType(t)}
            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${
              f.types.includes(t) ? "border-line-strong bg-surface-2 text-ink" : "border-line text-muted line-through"
            }`}
          >
            <span className={`size-2 rounded-full ${TYPE_BG[t]} ${f.types.includes(t) ? "" : "opacity-40"}`} aria-hidden />
            {TYPE_LABEL[t]}
          </button>
        ))}
      </div>
      <Segmented
        label="Scope"
        value={f.scope}
        onChange={(scope) => setFilters({ scope })}
        options={[
          { value: "all", label: "Any scope" },
          { value: "within-doc", label: "Within doc" },
          { value: "cross-doc", label: "Across docs" },
        ]}
      />
      <Select label="Family" value={f.family} onChange={(family) => setFilters({ family })}>
        <option value="all">All</option>
        {families.map((x) => (
          <option key={x.family} value={x.family}>
            {x.family}
          </option>
        ))}
      </Select>
      <Select label="Review" value={f.review} onChange={(v) => setFilters({ review: v as typeof f.review })}>
        <option value="all">All</option>
        <option value="unreviewed">Has unreviewed pairs</option>
        <option value="reviewed">Fully reviewed</option>
      </Select>
      <label className="inline-flex items-center gap-1.5 text-xs text-ink-2">
        <input
          type="checkbox"
          checked={f.numbersDiffer}
          onChange={(e) => setFilters({ numbersDiffer: e.target.checked })}
          className="accent-[var(--accent)]"
        />
        Figures differ
      </label>
      <div className="min-w-48 flex-1">
        <SearchBox value={f.search} onChange={(search) => setFilters({ search })} placeholder="Search text, section or document" />
      </div>
      <span className="text-xs text-muted">
        {clusters.length} / {total} groups · {queue.length} pairs
      </span>
      {changed && (
        <button onClick={() => setFilters(DEFAULT_FILTERS)} className="text-xs font-medium text-accent hover:underline">
          Reset
        </button>
      )}
    </div>
  );
}
