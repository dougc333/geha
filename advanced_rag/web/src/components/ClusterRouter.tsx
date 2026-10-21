import { AlertTriangle, Check, Database, History, LoaderCircle, Route, Send } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  ingestionApi,
  type ClusterRecord,
  type QueryExample,
  type QueryRouterResponse,
} from "../api";

const sample = '{"user_input":"Which employer benefit surveys report premium changes?"}';

function title(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function ClusterRouter() {
  const [clusters, setClusters] = useState<ClusterRecord[]>([]);
  const [examples, setExamples] = useState<QueryExample[]>([]);
  const [selectedExampleId, setSelectedExampleId] = useState("");
  const [jsonl, setJsonl] = useState(sample);
  const [result, setResult] = useState<QueryRouterResponse | null>(null);
  const [history, setHistory] = useState<QueryRouterResponse[]>([]);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([ingestionApi.clusters(), ingestionApi.routerRuns(), ingestionApi.queryExamples(30)])
      .then(([records, runs, queryExamples]) => {
        if (cancelled) return;
        setClusters(records);
        setHistory(runs);
        setExamples(queryExamples);
        if (runs[0]) {
          setResult(runs[0]);
          setJsonl(runs[0].input_jsonl);
          setSelectedRunId(runs[0].run_id);
        }
      })
      .catch((reason) => { if (!cancelled) setError(reason instanceof Error ? reason.message : "Could not load clusters"); });
    return () => { cancelled = true; };
  }, []);

  const selected = result?.routes[0]?.cluster;
  const totalDocuments = useMemo(
    () => clusters.reduce((sum, cluster) => sum + cluster.document_count, 0),
    [clusters],
  );
  const examplesByCluster = useMemo(() => {
    const grouped = new Map<string, QueryExample[]>();
    for (const example of examples) {
      grouped.set(example.cluster, [...(grouped.get(example.cluster) ?? []), example]);
    }
    return [...grouped.entries()];
  }, [examples]);

  async function submit() {
    setLoading(true);
    setError(null);
    try {
      const routed = await ingestionApi.routeJsonl(jsonl);
      setResult(routed);
      setHistory((runs) => [routed, ...runs.filter((run) => run.run_id !== routed.run_id)]);
      setSelectedRunId(routed.run_id);
    } catch (reason) {
      setResult(null);
      setError(reason instanceof Error ? reason.message : "Routing failed");
    } finally {
      setLoading(false);
    }
  }

  function showPreviousRun(runId: string) {
    setSelectedRunId(runId);
    const run = history.find((candidate) => candidate.run_id === runId);
    if (!run) return;
    setResult(run);
    setJsonl(run.input_jsonl);
    setError(null);
  }

  function chooseExample(exampleId: string) {
    setSelectedExampleId(exampleId);
    const example = examples.find((candidate) => candidate.id === exampleId);
    if (!example) return;
    setJsonl(JSON.stringify({ user_input: example.user_input }));
    setResult(null);
    setSelectedRunId("");
    setError(null);
  }

  return (
    <section className="panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-5 py-4">
        <div>
          <p className="eyebrow">Retrieval partitioning</p>
          <h2 className="mt-1 text-sm font-medium text-white">Document clusters &amp; JEV query router</h2>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {history.length > 0 && (
            <label className="flex items-center gap-2">
              <History size={13} className="text-citron" />
              <span className="sr-only">Previous router run</span>
              <select
                value={selectedRunId}
                onChange={(event) => showPreviousRun(event.target.value)}
                className="h-8 max-w-64 rounded-lg border border-white/10 bg-white/[.04] px-2 font-mono text-[9px] text-white outline-none focus:border-mint/50"
              >
                {history.map((run, index) => (
                  <option key={run.run_id} value={run.run_id}>
                    {index === 0 ? "Latest" : "Previous"} · {new Date(run.created_at).toLocaleString()} · {run.routes[0]?.cluster ?? "unrouted"}
                  </option>
                ))}
              </select>
            </label>
          )}
          <div className="flex items-center gap-2 font-mono text-[9px] uppercase tracking-[.12em] text-fog">
            <Database size={13} className="text-mint" />
            {clusters.length} clusters · {totalDocuments} documents
          </div>
        </div>
      </div>

      <div className="grid gap-px bg-white/10 sm:grid-cols-2 xl:grid-cols-3">
        {clusters.map((cluster) => (
          <article
            key={cluster.id}
            className={`bg-panel px-4 py-3.5 transition ${selected === cluster.id ? "relative z-10 bg-mint/[.08] ring-1 ring-inset ring-mint/60" : ""}`}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className={`text-xs font-semibold ${selected === cluster.id ? "text-mint" : "text-white"}`}>{cluster.label}</p>
                <p className="mt-1.5 line-clamp-2 text-[10px] leading-4 text-fog">{cluster.description}</p>
              </div>
              <span className="grid size-7 shrink-0 place-items-center rounded-lg border border-white/10 bg-white/[.04] font-mono text-[10px] text-white">{cluster.document_count}</span>
            </div>
            <p className="mt-2 font-mono text-[9px] text-fog/60">{cluster.destination}</p>
          </article>
        ))}
      </div>

      <div className="grid gap-0 border-t border-white/10 xl:grid-cols-[minmax(0,.9fr)_minmax(0,1.1fr)]">
        <div className="border-b border-white/10 p-5 xl:border-b-0 xl:border-r">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <p className="eyebrow">JSONL query input</p>
              <p className="mt-1 text-[10px] text-fog">One object per line · use user_input, query, or question</p>
            </div>
            <Route size={18} className="text-mint" />
          </div>
          <label className="mb-3 grid gap-1.5">
            <span className="font-mono text-[9px] uppercase tracking-[.12em] text-fog/70">Generated query · up to 30 across clusters</span>
            <select
              value={selectedExampleId}
              onChange={(event) => chooseExample(event.target.value)}
              className="h-9 w-full rounded-lg border border-white/10 bg-black/20 px-2.5 font-mono text-[10px] text-white outline-none focus:border-mint/50"
            >
              <option value="">Select a generated JSONL query</option>
              {examplesByCluster.map(([cluster, records]) => (
                <optgroup key={cluster} label={`${title(cluster)} (${records.length})`}>
                  {records.map((example) => (
                    <option key={example.id} value={example.id}>
                      {example.user_input.length > 105 ? `${example.user_input.slice(0, 102)}...` : example.user_input}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>
          <textarea
            value={jsonl}
            onChange={(event) => { setJsonl(event.target.value); setSelectedExampleId(""); }}
            spellCheck={false}
            className="min-h-32 w-full resize-y rounded-xl border border-white/10 bg-black/20 p-3 font-mono text-[11px] leading-5 text-white outline-none transition placeholder:text-fog/60 focus:border-mint/50 focus:ring-2 focus:ring-mint/10"
          />
          <div className="mt-3 flex items-center justify-between gap-3">
            <span className="font-mono text-[9px] uppercase tracking-[.12em] text-fog/70">
              {jsonl.split("\n").filter((line) => line.trim()).length} record(s)
            </span>
            <button type="button" onClick={submit} disabled={loading} className="button-primary disabled:cursor-wait disabled:opacity-60">
              {loading ? <LoaderCircle size={14} className="animate-spin" /> : <Send size={14} />}
              {loading ? "Routing" : "Route query"}
            </button>
          </div>
          {error && (
            <div className="mt-3 flex items-start gap-2 rounded-xl border border-amber-400/20 bg-amber-400/[.08] p-3 text-[10px] leading-4 text-amber-200">
              <AlertTriangle size={14} className="mt-px shrink-0" /> {error}
            </div>
          )}
        </div>

        <div className="min-w-0 p-5">
          {!result ? (
            <div className="grid min-h-52 place-items-center rounded-xl border border-dashed border-white/10 bg-white/[.015] px-8 text-center">
              <div>
                <Route size={22} className="mx-auto text-fog/60" />
                <p className="mt-3 text-xs text-fog">Submit a JSONL query to inspect validation, classification, and cluster routing.</p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="eyebrow">Router status</p>
                  <p className="mt-1 font-mono text-[10px] text-fog">{result.router.name} · {new Date(result.created_at).toLocaleString()}</p>
                </div>
                <span className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 font-mono text-[9px] uppercase tracking-[.1em] ${result.router.mode === "jev" ? "border-mint/30 bg-mint/[.08] text-mint" : "border-amber-400/30 bg-amber-400/[.08] text-amber-200"}`}>
                  <span className={`size-1.5 rounded-full ${result.router.mode === "jev" ? "bg-mint" : "bg-amber-300"}`} />
                  {result.router.mode === "jev" ? "JEV online" : result.router.jev_available ? "JEV error · fallback active" : "JEV unavailable · fallback active"}
                </span>
              </div>

              <div className="flex flex-wrap gap-2">
                {result.events.map((event, index) => (
                  <div key={`${event.stage}-${index}`} className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[.035] px-2.5 py-2 font-mono text-[9px] uppercase tracking-[.08em] text-fog">
                    <Check size={11} className="text-mint" /> {event.stage.replaceAll("_", " ")}
                  </div>
                ))}
              </div>

              {result.routes.map((route) => (
                <article key={route.line} className="rounded-xl border border-mint/20 bg-mint/[.045] p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-mono text-[9px] uppercase tracking-[.12em] text-fog">Line {route.line} · {route.method.replaceAll("_", " ")}</p>
                      <p className="mt-1 truncate text-xs text-white" title={route.query}>{route.query}</p>
                    </div>
                    <div className="shrink-0 text-right">
                      <p className="text-sm font-semibold text-mint">{title(route.cluster)}</p>
                      <p className="font-mono text-[9px] text-fog">{(route.confidence * 100).toFixed(1)}% confidence</p>
                    </div>
                  </div>
                  <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
                    <div className="h-full rounded-full bg-mint" style={{ width: `${Math.max(3, route.confidence * 100)}%` }} />
                  </div>
                  <div className="mt-3 grid gap-3 sm:grid-cols-2">
                    <div>
                      <p className="eyebrow">Routing evidence</p>
                      <div className="mt-1.5 flex flex-wrap gap-1.5">
                        {route.signals.map((signal) => <span key={signal} className="rounded-md bg-white/[.06] px-2 py-1 font-mono text-[9px] text-white/80">{signal}</span>)}
                      </div>
                    </div>
                    <div>
                      <p className="eyebrow">Search destination</p>
                      <p className="mt-1.5 rounded-md bg-black/20 px-2 py-1.5 font-mono text-[10px] text-citron">{route.destination}</p>
                    </div>
                  </div>
                  <div className="mt-3">
                    <p className="eyebrow">Cluster probabilities</p>
                    <div className="mt-2 grid gap-1.5 sm:grid-cols-2">
                      {Object.entries(route.probabilities)
                        .sort((left, right) => right[1] - left[1])
                        .map(([cluster, probability]) => (
                          <div key={cluster} className="grid grid-cols-[104px_1fr_38px] items-center gap-2 font-mono text-[9px] text-fog">
                            <span className={cluster === route.cluster ? "text-mint" : ""}>{cluster.replaceAll("_", " ")}</span>
                            <span className="h-1 overflow-hidden rounded-full bg-white/10"><span className="block h-full rounded-full bg-mint/70" style={{ width: `${Math.max(2, probability * 100)}%` }} /></span>
                            <span className="text-right">{(probability * 100).toFixed(1)}%</span>
                          </div>
                        ))}
                    </div>
                  </div>
                </article>
              ))}
              {result.router.mode !== "jev" && (
                <p className="text-[10px] leading-4 text-fog">
                  {result.router.fallback_reason ?? <>TypeSafe Jev requires both <code className="text-white">typesafe-sdk</code> and <code className="text-white">TYPESAFE_API_KEY</code>.</>} The current result uses visible keyword signals and is labeled as a fallback.
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
