import { useMemo } from "react";
import type { Cluster, Edge } from "../lib/schema";
import { filterClusters, useStore } from "../store/useStore";

/** Clusters passing the explorer filters, and the flat list of their pairs
 * (the review queue the compare view steps through). */
export function useFilteredClusters(): { clusters: Cluster[]; queue: Edge[] } {
  const all = useStore((s) => s.report?.clusters);
  const filters = useStore((s) => s.filters);
  const verdicts = useStore((s) => s.verdicts);
  const docs = useStore((s) => s.docs);
  return useMemo(() => {
    const clusters = filterClusters(all ?? [], filters, verdicts, docs);
    // The queue holds only the pairs the filters are about: a "near only,
    // figures differ" review should not step through the exact copies.
    const queue = clusters.flatMap((c) =>
      c.edges.filter(
        (e) =>
          filters.types.includes(e.type) &&
          (filters.scope === "all" || e.scope === filters.scope) &&
          (!filters.numbersDiffer || e.numbersDiffer),
      ),
    );
    return { clusters, queue };
  }, [all, filters, verdicts, docs]);
}
